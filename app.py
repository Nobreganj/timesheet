from flask import Flask, request, render_template, redirect, jsonify
from simple_salesforce import Salesforce
import os

app = Flask(__name__)

def authenticate_salesforce():
    return Salesforce(
        username=os.environ['SALESFORCE_USERNAME'],
        password=os.environ['SALESFORCE_PASSWORD'],
        security_token=os.environ['SALESFORCE_SECURITY_TOKEN'],
        domain='login'  # Use 'test' if you're using Salesforce sandbox
    )

sf = authenticate_salesforce()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    global sf
    try:
        # Capture form data
        data = request.form.to_dict()

        # If the proposal field exists, format it to include "P-"
        if 'Proposal__c' in data and data['Proposal__c']:
            data['Proposal__c'] = 'P-' + data['Proposal__c']

        # Attempt to create a record in Salesforce
        sf.Timesheet__c.create(data)

        return jsonify({"status": "success", "message": "Thank you, your timesheet has been submitted!"})
    except Exception as e:
        # Check if the session has expired or is invalid, and re-authenticate if necessary
        if 'INVALID_SESSION_ID' in str(e):
            sf = authenticate_salesforce()  # Re-authenticate
            try:
                sf.Timesheet__c.create(data)  # Retry the operation
                return jsonify({"status": "success", "message": "Thank you, your timesheet has been submitted!"})
            except Exception as retry_error:
                return jsonify({"status": "error", "message": str(retry_error)})
        else:
            return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
