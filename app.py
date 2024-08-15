from flask import Flask, request, render_template, redirect
from simple_salesforce import Salesforce
import os

app = Flask(__name__)

# Salesforce authentication
sf = Salesforce(
    username=os.environ['SALESFORCE_USERNAME'],
    password=os.environ['SALESFORCE_PASSWORD'],
    security_token=os.environ['SALESFORCE_SECURITY_TOKEN'],
    domain='login'  # Use 'test' if you're using Salesforce sandbox
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    # Capture form data
    data = {
        'Start_Date__c': request.form['Start_Date__c'],
        'End_Date__c': request.form['End_Date__c'],
        'Users__c': request.form['Users__c'],
        'Hours_Spent__c': request.form['Hours_Spent__c'],
        'Work_Type__c': request.form['Work_Type__c'],
        'Work_Description__c': request.form['Work_Description__c'],
        'Proposal__c': request.form['Proposal__c'],
        'Account__c': request.form['Account__c']
    }

    # Create a record in Salesforce
    try:
        sf.Timesheet__c.create(data)
        return redirect('/')
    except Exception as e:
        return f"An error occurred: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)
