from odoo import _, api, fields, models
from odoo.exceptions import UserError


_STEPS = [
    ('draft', 'Identificación'),
    ('rooming', 'Ubicación'),
    ('medical', 'Médico'),
    ('psych', 'Psicología'),
    ('nursing', 'Enfermería'),
    ('docs', 'Documentación'),
    ('economy', 'Economía'),
    ('done', 'Cerrado'),
]

_NEXT = {
    'draft': 'rooming',
    'rooming': 'medical',
    'medical': 'psych',
    'psych': 'nursing',
    'nursing': 'docs',
    'docs': 'economy',
    'economy': 'done',
}

_PREV = {v: k for k, v in _NEXT.items()}


class AdmissionProcess(models.Model):
    _name = 'cs.admission.process'
    _description = 'Proceso de Admisión'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default=lambda self: _('Nueva Admisión'),
        readonly=True,
    )
    state = fields.Selection(
        _STEPS,
        string='Paso',
        default='draft',
        tracking=True,
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )

    # ── Paso 1: Identificación ─────────────────────────────────────────
    full_name = fields.Char(string='Nombre completo', tracking=True)
    dni = fields.Char(string='DNI / NIF', tracking=True)
    fecha_nacimiento = fields.Date(string='Fecha de nacimiento')
    phone = fields.Char(string='Teléfono')
    email_contact = fields.Char(string='Email')
    guardian_name = fields.Char(string='Tutor legal / Familiar responsable')
    guardian_phone = fields.Char(string='Teléfono tutor')
    guardian_email = fields.Char(string='Email tutor')
    identification_notes = fields.Text(string='Notas de identificación')

    resident_id = fields.Many2one(
        'cs.resident',
        string='Residente',
        tracking=True,
        copy=False,
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='resident_id.partner_id',
        store=True,
        readonly=True,
    )

    # ── Paso 2: Ubicación ──────────────────────────────────────────────
    admission_date = fields.Date(
        string='Fecha de ingreso',
        default=fields.Date.context_today,
        tracking=True,
    )
    residence_id = fields.Many2one('cs.residence', string='Residencia', tracking=True)
    room_id = fields.Many2one(
        'cs.room',
        string='Habitación',
        tracking=True,
        domain="[('residence_id', '=', residence_id), ('state', '=', 'disponible')]",
    )

    # ── Paso 3: Médico ─────────────────────────────────────────────────
    medical_consultation_id = fields.Many2one(
        'cs.medical.consultation',
        string='Consulta médica de ingreso',
        copy=False,
        domain="[('resident_id', '=', resident_id)]",
    )

    # ── Paso 4: Psicología ─────────────────────────────────────────────
    initial_assessment_id = fields.Many2one(
        'cs.initial.assessment',
        string='Evaluación psicológica inicial',
        copy=False,
        domain="[('resident_id', '=', resident_id)]",
    )

    # ── Paso 5: Enfermería ─────────────────────────────────────────────
    allergies = fields.Text(string='Alergias conocidas')
    current_medications = fields.Text(string='Medicación actual al ingreso')
    test_alcohol = fields.Boolean(string='Test alcohol realizado')
    test_alcohol_result = fields.Char(string='Resultado alcohol')
    test_drugs = fields.Boolean(string='Test multidrogas realizado')
    test_drugs_result = fields.Char(string='Resultado multidrogas')
    nursing_notes = fields.Text(string='Notas de enfermería')

    # ── Paso 6: Documentación ──────────────────────────────────────────
    doc_id_provided = fields.Boolean(string='DNI / pasaporte entregado')
    doc_contract_signed = fields.Boolean(string='Contrato de ingreso firmado')
    doc_medical_report = fields.Boolean(string='Informe médico previo entregado')
    doc_consent_signed = fields.Boolean(string='Consentimiento informado firmado')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'cs_admission_attachment_rel',
        'admission_id',
        'attachment_id',
        string='Documentos adjuntos',
    )

    # ── Paso 7: Economía ───────────────────────────────────────────────
    wallet_id = fields.Many2one(
        'patient.wallet.account',
        string='Cartera del paciente',
        copy=False,
        domain="[('patient_id', '=', partner_id)]",
    )

    # ── Paso 8: Cierre ─────────────────────────────────────────────────
    closing_notes = fields.Text(string='Notas de cierre')
    closed_date = fields.Date(string='Fecha de cierre', readonly=True)

    # ── Navegación ─────────────────────────────────────────────────────

    def _validate_current_step(self):
        self.ensure_one()
        if self.state == 'draft':
            if not self.full_name or not self.dni:
                raise UserError(_('Nombre completo y DNI son obligatorios para continuar.'))
        elif self.state == 'rooming':
            if not self.residence_id:
                raise UserError(_('Debe seleccionar una residencia antes de continuar.'))

    def action_next_step(self):
        for rec in self:
            rec._validate_current_step()
            if rec.state == 'draft' and not rec.resident_id:
                rec._create_resident()
            elif rec.state == 'rooming':
                rec._apply_location()
            next_state = _NEXT.get(rec.state)
            if next_state:
                if next_state == 'done':
                    rec._close_admission()
                else:
                    rec.state = next_state
        return True

    def action_prev_step(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(_('No se puede reabrir una admisión ya cerrada.'))
            prev_state = _PREV.get(rec.state)
            if prev_state:
                rec.state = prev_state
        return True

    def action_complete_admission(self):
        """Botón final: cierra la admisión desde el paso Economía."""
        for rec in self:
            if rec.state != 'economy':
                raise UserError(_('Solo se puede completar la admisión desde el paso Economía.'))
            rec._validate_current_step()
            rec._close_admission()
        return True

    # ── Acciones sobre registros vinculados ────────────────────────────

    def action_open_resident(self):
        self.ensure_one()
        if not self.resident_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cs.resident',
            'res_id': self.resident_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_medical(self):
        self.ensure_one()
        if not self.medical_consultation_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cs.medical.consultation',
            'res_id': self.medical_consultation_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_new_medical_consultation(self):
        """Abre el formulario de nueva consulta médica pre-relleno con el residente."""
        self.ensure_one()
        if not self.resident_id:
            raise UserError(_('Cree primero el residente completando el paso de Identificación.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cs.medical.consultation',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_resident_id': self.resident_id.id,
                'default_consultation_type': 'general',
                'default_admission_id': self.id,
            },
        }

    def action_create_initial_assessment(self):
        """Crea la evaluación psicológica inicial y la abre."""
        self.ensure_one()
        if self.initial_assessment_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'cs.initial.assessment',
                'res_id': self.initial_assessment_id.id,
                'view_mode': 'form',
                'target': 'new',
            }
        if not self.resident_id:
            raise UserError(_('Cree primero el residente completando el paso de Identificación.'))
        assessment = self.env['cs.initial.assessment'].create({
            'resident_id': self.resident_id.id,
        })
        self.initial_assessment_id = assessment.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cs.initial.assessment',
            'res_id': assessment.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_create_wallet(self):
        """Crea la cartera del paciente si no existe y la abre."""
        self.ensure_one()
        if self.wallet_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'patient.wallet.account',
                'res_id': self.wallet_id.id,
                'view_mode': 'form',
                'target': 'new',
            }
        if not self.partner_id:
            raise UserError(_('Cree primero el residente completando el paso de Identificación.'))
        existing = self.env['patient.wallet.account'].search([
            ('patient_id', '=', self.partner_id.id),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if existing:
            self.wallet_id = existing.id
        else:
            wallet = self.env['patient.wallet.account'].create({
                'patient_id': self.partner_id.id,
                'responsible_id': self.env.user.id,
                'company_id': self.company_id.id,
            })
            self.wallet_id = wallet.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'patient.wallet.account',
            'res_id': self.wallet_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ── Helpers internos ───────────────────────────────────────────────

    def _create_resident(self):
        """Crea cs.resident + res.partner a partir de los datos del paso 1."""
        self.ensure_one()
        category = self.env['res.partner.category'].search(
            [('name', '=', 'Paciente')], limit=1
        )
        if not category:
            category = self.env['res.partner.category'].create({'name': 'Paciente'})

        partner = self.env['res.partner'].create({
            'name': self.full_name,
            'vat': self.dni,
            'phone': self.phone or '',
            'email': self.email_contact or '',
            'category_id': [(4, category.id)],
        })

        if self.guardian_name:
            existing = self.env['res.partner'].search([
                ('name', '=', self.guardian_name),
                ('parent_id', '=', partner.id),
            ], limit=1)
            if not existing:
                self.env['res.partner'].create({
                    'name': self.guardian_name,
                    'phone': self.guardian_phone or '',
                    'email': self.guardian_email or '',
                    'parent_id': partner.id,
                    'type': 'contact',
                })

        resident = self.env['cs.resident'].create({
            'name': self.full_name,
            'dni': self.dni,
            'fecha_nacimiento': self.fecha_nacimiento,
            'phone': self.phone or '',
            'partner_id': partner.id,
            'state': 'activo',
        })
        self.resident_id = resident.id

    def _apply_location(self):
        """Escribe residencia y habitación en el residente."""
        self.ensure_one()
        if not self.resident_id:
            return
        vals = {}
        if self.residence_id:
            vals['residence_id'] = self.residence_id.id
        if self.room_id:
            vals['room_id'] = self.room_id.id
        if vals:
            self.resident_id.write(vals)

    def _close_admission(self):
        self.ensure_one()
        self.state = 'done'
        self.closed_date = fields.Date.context_today(self)
        self.message_post(body=_('Admisión completada. Residente activado en el sistema.'))
        if self.resident_id:
            nursing_fields = {
                'allergies': self.allergies,
                'current_medications': self.current_medications,
                'nursing_notes': self.nursing_notes,
                'test_alcohol': self.test_alcohol,
                'test_alcohol_result': self.test_alcohol_result,
                'test_drugs': self.test_drugs,
                'test_drugs_result': self.test_drugs_result,
            }
            resident_fnames = self.resident_id._fields
            vals = {k: v for k, v in nursing_fields.items() if k in resident_fnames and v}
            if vals:
                self.resident_id.write(vals)
        if self.resident_id and 'cs.piai' in self.env:
            existing = self.env['cs.piai'].search([
                ('resident_id', '=', self.resident_id.id),
                ('state', '!=', 'closed_discharge'),
            ], limit=1)
            if not existing:
                self.env['cs.piai'].create({
                    'resident_id': self.resident_id.id,
                    'state': 'draft',
                    'therapeutic_phase': 'acogida',
                    'date_elaboration': fields.Date.context_today(self),
                })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name') in (False, _('Nueva Admisión')):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('cs.admission.process')
                    or _('Nueva Admisión')
                )
        return super().create(vals_list)
