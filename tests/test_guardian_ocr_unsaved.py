from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGuardianOcrUnsaved(TransactionCase):

    def test_ocr_on_unsaved_guardian_warns_user(self):
        guardian = self.env['cs.admission.guardian'].new({'name': 'Tutor sin guardar'})
        with self.assertRaises(UserError):
            guardian.action_process_ocr()
