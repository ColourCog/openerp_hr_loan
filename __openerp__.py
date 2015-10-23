{
    "name" : "Loan Management",
    "version" : "2.0", 
    "category" : "Human Resources", 
    "sequence": 40,
    "complexity" : "normal", 
    "author" : "ColourCog.com", 
    "website" : "http://colourcog.com", 
    "depends" : [
        "base", 
        "hr", 
        "hr_contract", 
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
      "security/hr_loan_security.xml",
      "security/ir.model.access.csv",
      'hr_loan_view.xml', 
      'res_config_view.xml', 
      'hr_view.xml', 
      'hr_loan_sequence.xml', 
      'hr_loan_workflow.xml', 
      'hr_loan_data.xml', 
      'hr_loan_report.xml', 
    ], 
    'demo': ['hr_loan_demo.xml'],
    'installable': True,
    'auto_install': False,
    'application': False,
}

