{
    'name': 'Centro Sanitario - Admisión',
    'version': '1.0.0',
    'category': 'Healthcare',
    'summary': 'Asistente guiado de admisión de residentes para Equilibrium',
    'author': 'Equilibrium Dev Team',
    'license': 'LGPL-3',
    'depends': [
        'cs_resident',
        'cs_medical_care',
        'cs_psychology',
        'cs_purse_pocket',
        'cs_patient_followup_forms',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/admission_process_views.xml',
        'views/admission_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
