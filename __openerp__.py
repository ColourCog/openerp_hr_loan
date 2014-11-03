{
    "name" : "Loan Management",
    "version" : "1.0", 
    "category" : "Human Resources", 
    "complexity" : "normal", 
    "author" : "ColourCog.com", 
    "website" : "http://colourcog.com", 
    "depends" : [
        "base", 
        "hr", 
        "hr_payroll",
        "hr_payroll_account",
        "account",
    ], 
    "summary" : "Management for Employee Loans", 
    "description" : """
Employee Loan Management
========================
This module adds loan management capabilities to the Human Rssources section
in OpenERP.

    """,
    "data" : [ 
      'security/hr_loan_security.xml', 
      'hr_loan_view.xml', 
      'hr_view.xml', 
      'hr_loan_sequence.xml', 
      'hr_loan_workflow.xml', 
      'hr_loan_data.xml', 
    ], 
    "application": False, 
    "installable": True
}

