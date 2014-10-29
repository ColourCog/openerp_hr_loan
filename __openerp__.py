{
    "name" : "Loan Management",
    "version" : "1.0", 
    "category" : "HR", 
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
    "description" : "Management for Employee Loans",
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

