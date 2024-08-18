from flask import Flask, request, render_template, jsonify
from simple_salesforce import Salesforce
import os

app = Flask(__name__)

# Function to authenticate and connect to Salesforce
def authenticate_salesforce():
    return Salesforce(
        username=os.environ['SALESFORCE_USERNAME'],
        password=os.environ['SALESFORCE_PASSWORD'],
        security_token=os.environ['SALESFORCE_SECURITY_TOKEN'],
        domain='login'  # Use 'test' if you're using Salesforce sandbox
    )

# Authenticate and create a Salesforce session
sf = authenticate_salesforce()

@app.route('/')
def index():
    return render_template('index.html')

# Route to get proposals from Salesforce
@app.route('/get_proposals', methods=['GET'])
def get_proposals():
    try:
        # Query Salesforce for Proposal records
        proposals = sf.query_all("SELECT Id, Name FROM Proposal__c")

        # Create a list of proposals with their ID and Name
        proposal_list = [{"id": record["Id"], "name": record["Name"]} for record in proposals["records"]]

        return jsonify({"proposals": proposal_list}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/submit', methods=['POST'])
def submit():
    global sf
    try:
        # Capture form data
        data = {
            'Start_Date__c': request.form['Start_Date__c'],
            'End_Date__c': request.form['End_Date__c'],
            'Users__c': request.form['Users__c'],
            'Hours_Spent__c': request.form['Hours_Spent__c'],
            'Work_Type__c': request.form['Work_Type__c'],
            'Work_Description__c': request.form['Work_Description__c'],
            'Proposals__c': request.form['Proposals__c'],
            'Account__c': request.form['Account__c']
        }

        # Attempt to create a record in Salesforce
        sf.Timesheet__c.create(data)

        return render_template('success.html')  # Replace with your success page
    except Exception as e:
        # Check if the session has expired or is invalid, and re-authenticate if necessary
        if 'INVALID_SESSION_ID' in str(e):
            sf = authenticate_salesforce()  # Re-authenticate
            try:
                sf.Timesheet__c.create(data)  # Retry the operation
                return render_template('success.html')  # Replace with your success page
            except Exception as retry_error:
                return f"An error occurred: {str(retry_error)}"
        else:
            return f"An error occurred: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)
