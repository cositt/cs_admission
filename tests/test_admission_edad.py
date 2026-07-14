from dateutil.relativedelta import relativedelta

from odoo.fields import Date
from odoo.tests.common import TransactionCase


class TestAdmissionEdad(TransactionCase):

    def _make_admission(self, fecha_nacimiento=None):
        return self.env['cs.admission.process'].create({
            'full_name': 'Paciente Test Edad',
            'fecha_nacimiento': fecha_nacimiento,
        })

    def test_sin_fecha_nacimiento(self):
        admision = self._make_admission()
        self.assertEqual(admision.edad, 0)
        self.assertFalse(admision.es_menor)

    def test_adulto(self):
        nacimiento = Date.context_today(self.env.user) - relativedelta(years=25)
        admision = self._make_admission(nacimiento)
        self.assertEqual(admision.edad, 25)
        self.assertFalse(admision.es_menor)

    def test_menor(self):
        nacimiento = Date.context_today(self.env.user) - relativedelta(years=10)
        admision = self._make_admission(nacimiento)
        self.assertEqual(admision.edad, 10)
        self.assertTrue(admision.es_menor)

    def test_cumple_18_hoy_no_es_menor(self):
        nacimiento = Date.context_today(self.env.user) - relativedelta(years=18)
        admision = self._make_admission(nacimiento)
        self.assertEqual(admision.edad, 18)
        self.assertFalse(admision.es_menor)

    def test_cumple_18_manana_sigue_siendo_menor(self):
        nacimiento = Date.context_today(self.env.user) - relativedelta(years=18) + relativedelta(days=1)
        admision = self._make_admission(nacimiento)
        self.assertEqual(admision.edad, 17)
        self.assertTrue(admision.es_menor)
