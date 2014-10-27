{
    "name" : "Loan Management",
    "version" : "1.0", 
    "category" : "HR", 
    "complexity" : "normal", 
    "author" : "ColourCog.com", 
    "website" : "http://colourcog.com", 
    "depends" : ["base", "hr", "hr_contract", "hr_expense"], 
    "summary" : "Management for Employee Loans", 
    "description" : "Management for Employee Loans",
    "data" : [ 
      'security/hr_loan_security.xml', 
      'hr_loan_view.xml', 
      'hr_loan_sequence.xml', 
    ], 
    "application": False, 
    "installable": True
}

