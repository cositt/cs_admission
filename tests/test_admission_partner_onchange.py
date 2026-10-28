from odoo.tests.common import TransactionCase


class TestAdmissionPartnerOnchange(TransactionCase):
    """Odoo 19 eliminó res.partner.mobile: los onchange de contacto no deben usarlo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Contacto Onchange Test',
            'phone': '600111222',
            'email': 'onchange@example.com',
            'street': 'Calle Prueba 1',
            'city': 'Ronda',
        })
        cls.partner_sin_telefono = cls.env['res.partner'].create({
            'name': 'Contacto Sin Telefono',
        })

    def test_proceso_copia_datos_del_contacto(self):
        admision = self.env['cs.admission.process'].new({
            'patient_partner_id': self.partner.id,
        })
        admision._onchange_patient_partner_id()
        self.assertEqual(admision.full_name, 'Contacto Onchange Test')
        self.assertEqual(admision.phone, '600111222')
        self.assertEqual(admision.email_contact, 'onchange@example.com')
        self.assertEqual(admision.city, 'Ronda')

    def test_proceso_conserva_telefono_si_contacto_no_tiene(self):
        admision = self.env['cs.admission.process'].new({
            'phone': '955000000',
            'patient_partner_id': self.partner_sin_telefono.id,
        })
        admision._onchange_patient_partner_id()
        self.assertEqual(admision.phone, '955000000')

    def test_tutor_copia_datos_del_contacto(self):
        tutor = self.env['cs.admission.guardian'].new({
            'partner_id': self.partner.id,
        })
        tutor._onchange_partner_id()
        self.assertEqual(tutor.name, 'Contacto Onchange Test')
        self.assertEqual(tutor.phone, '600111222')
        self.assertEqual(tutor.email, 'onchange@example.com')

    def test_tutor_conserva_telefono_si_contacto_no_tiene(self):
        tutor = self.env['cs.admission.guardian'].new({
            'phone': '955000000',
            'partner_id': self.partner_sin_telefono.id,
        })
        tutor._onchange_partner_id()
        self.assertEqual(tutor.phone, '955000000')
