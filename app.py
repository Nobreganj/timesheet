from flask import Flask, request, render_template, redirect, url_for, abort
from simple_salesforce import Salesforce
from itsdangerous import URLSafeSerializer, BadSignature
from werkzeug.middleware.proxy_fix import ProxyFix
from collections import OrderedDict
from datetime import date
import os

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # so links built behind the host's proxy use https

def authenticate_salesforce():
    return Salesforce(
        username=os.environ['SALESFORCE_USERNAME'],
        password=os.environ['SALESFORCE_PASSWORD'],
        security_token=os.environ['SALESFORCE_SECURITY_TOKEN'],
        domain='login'  # Use 'test' if you're using Salesforce sandbox
    )

sf = authenticate_salesforce()

# "My timesheets" portal: everyone gets a private link, signed with PORTAL_SECRET, that shows their own entries.
# The link is only ever delivered in the Salesforce confirmation email (stored in PORTAL_LINK_FIELD, e.g. Portal_Link__c),
# never shown on a page: the form has no login, so anyone can type anyone's name.
# Until both settings exist the portal is switched off and submissions behave exactly as before.
PORTAL_SECRET = os.environ.get('PORTAL_SECRET')
PORTAL_LINK_FIELD = os.environ.get('PORTAL_LINK_FIELD')
portal_signer = URLSafeSerializer(PORTAL_SECRET, salt='my-timesheets') if PORTAL_SECRET else None

PORTAL_FIELDS = ['Start_Date__c', 'Hours_Spent__c', 'Project_Work_Type__c', 'Work_Type__c',
                 'Account__c', 'Proposal__c', 'Work_Description__c']
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
               'August', 'September', 'October', 'November', 'December']

def portal_url_for(user):
    """Private portal link for a user, or None. Never raises, so it can't block a submission."""
    try:
        user = (user or '').strip()
        if not portal_signer or not user:
            return None
        return url_for('my_timesheets', token=portal_signer.dumps(user), _external=True)
    except Exception:
        app.logger.exception('Could not build portal link')
        return None

def soql_quote(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"

def query_all(soql):
    global sf
    try:
        return sf.query_all(soql)['records']
    except Exception as e:
        if 'INVALID_SESSION_ID' not in str(e):
            raise
        sf = authenticate_salesforce()  # Re-authenticate, same as submit()
        return sf.query_all(soql)['records']

@app.template_filter('hours')
def format_hours(value):
    return ('%.2f' % (value or 0)).rstrip('0').rstrip('.')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    global sf
    try:
        # Capture form data
        data = request.form.to_dict()

        # Store the private history link on the record so only the confirmation email carries it
        link_emailed = False
        if PORTAL_LINK_FIELD:
            portal_url = portal_url_for(data.get('Users__c'))
            if portal_url:
                data[PORTAL_LINK_FIELD] = portal_url
                link_emailed = True

        # Attempt to create a record in Salesforce
        sf.Timesheet__c.create(data)

        # After successful submission, render a thank you page
        return render_template('thank_you.html', link_emailed=link_emailed)

    except Exception as e:
        # Check if the session has expired or is invalid, and re-authenticate if necessary
        if 'INVALID_SESSION_ID' in str(e):
            sf = authenticate_salesforce()  # Re-authenticate
            try:
                sf.Timesheet__c.create(data)  # Retry the operation
                return render_template('thank_you.html', link_emailed=link_emailed)
            except Exception as retry_error:
                return f"An error occurred: {str(retry_error)}"
        else:
            return f"An error occurred: {str(e)}"

@app.route('/my-timesheets/<token>')
def my_timesheets(token):
    if not portal_signer:
        abort(404)
    try:
        user = portal_signer.loads(token)
    except BadSignature:
        return render_template('my_timesheets.html', state='invalid'), 404

    try:
        records = query_all(
            'SELECT ' + ', '.join(PORTAL_FIELDS) + ' FROM Timesheet__c'
            ' WHERE Users__c = ' + soql_quote(user) +
            ' ORDER BY Start_Date__c DESC, CreatedDate DESC')
    except Exception:
        app.logger.exception('Could not load timesheets')
        return render_template('my_timesheets.html', state='error', user=user), 503

    entries = []
    for r in records:
        if not r.get('Start_Date__c'):
            continue
        d = date.fromisoformat(r['Start_Date__c'][:10])
        entries.append({
            'date': d,
            'hours': r.get('Hours_Spent__c') or 0,
            'project_work_type': r.get('Project_Work_Type__c'),
            'work_type': r.get('Work_Type__c'),
            'account': r.get('Account__c'),
            'proposal': r.get('Proposal__c'),
            'description': r.get('Work_Description__c'),
        })

    year_totals = OrderedDict()
    for e in entries:  # newest first, so years come out newest first
        year_totals[e['date'].year] = year_totals.get(e['date'].year, 0) + e['hours']

    this_year = date.today().year
    year = request.args.get('year', type=int)
    if year not in year_totals:
        year = this_year if (this_year in year_totals or not year_totals) else next(iter(year_totals))

    in_year = [e for e in entries if e['date'].year == year]
    month_hours = [0] * 12
    months = OrderedDict()
    for e in in_year:
        month_hours[e['date'].month - 1] += e['hours']
        months.setdefault(e['date'].month, []).append(e)

    peak = max(month_hours)
    bars = [{'label': MONTHS[i], 'name': MONTH_NAMES[i], 'hours': h,
             'pct': round(h / peak * 100, 1) if peak else 0}
            for i, h in enumerate(month_hours)]

    return render_template(
        'my_timesheets.html',
        state='ok' if entries else 'empty',
        user=user,
        first_name=user.split()[0],
        year=year,
        year_totals=year_totals,
        total_hours=year_totals.get(year, 0),
        entry_count=len(in_year),
        busiest=MONTH_NAMES[month_hours.index(peak)] if peak else None,
        bars=bars,
        months=[(MONTH_NAMES[m - 1], sum(e['hours'] for e in items), items) for m, items in months.items()],
    )

if __name__ == '__main__':
    app.run(debug=True)
