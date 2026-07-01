from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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
    _inherit = ['mail.thread', 'mail.activity.mixin', 'dni.ocr.engine']
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
    patient_partner_id = fields.Many2one(
        'res.partner',
        string='Contacto paciente existente',
        tracking=True,
        help='Seleccione un contacto ya registrado o rellene los datos para crear uno nuevo.',
    )
    full_name = fields.Char(string='Nombre completo', tracking=True)
    dni = fields.Char(string='DNI / NIF', tracking=True)
    fecha_nacimiento = fields.Date(string='Fecha de nacimiento')
    phone = fields.Char(string='Teléfono')
    email_contact = fields.Char(string='Email')
    identification_notes = fields.Text(string='Notas de identificación')

    patient_ocr_front_image = fields.Binary(string='DNI paciente anverso', attachment=True)
    patient_ocr_front_filename = fields.Char(string='Nombre anverso paciente')
    patient_ocr_back_image = fields.Binary(string='DNI paciente reverso', attachment=True)
    patient_ocr_back_filename = fields.Char(string='Nombre reverso paciente')
    patient_ocr_state = fields.Selection(
        [
            ('none', 'Sin OCR'),
            ('processed', 'Procesado'),
            ('review', 'Revisión'),
        ],
        string='Estado OCR paciente',
        default='none',
        readonly=True,
    )
    patient_ocr_front_text = fields.Text(string='Texto OCR anverso', readonly=True)
    patient_ocr_back_text = fields.Text(string='Texto OCR reverso', readonly=True)
    patient_ocr_show_review_text = fields.Boolean(
        string='Texto OCR (revisión)',
        default=False,
        help='Mostrar el texto bruto del OCR para revisión manual.',
    )

    guardian_ids = fields.One2many(
        'cs.admission.guardian',
        'admission_id',
        string='Tutores / familiares',
    )

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

    @api.onchange('patient_partner_id')
    def _onchange_patient_partner_id(self):
        if not self.patient_partner_id:
            return
        partner = self.patient_partner_id
        self.full_name = partner.name or self.full_name
        self.dni = partner.vat or partner.ref or self.dni
        self.phone = partner.phone or partner.mobile or self.phone
        self.email_contact = partner.email or self.email_contact
        existing_resident = self.env['cs.resident'].search([
            ('partner_id', '=', partner.id),
        ], limit=1)
        if existing_resident:
            self.resident_id = existing_resident
            if existing_resident.fecha_nacimiento:
                self.fecha_nacimiento = existing_resident.fecha_nacimiento

    def _ocr_apply_patient_result(self, result):
        self.ensure_one()
        vals = {
            'patient_ocr_state': result['state'],
            'patient_ocr_front_text': result.get('front_text') or '',
            'patient_ocr_back_text': result.get('back_text') or '',
        }
        if result.get('dni_number'):
            vals['dni'] = result['dni_number']
        if result.get('full_name'):
            vals['full_name'] = result['full_name']
        if result.get('birth_date'):
            vals['fecha_nacimiento'] = result['birth_date']
        self.write(vals)

    def _ocr_reload_form_action(self, title, message, msg_type='warning'):
        self.ensure_one()
        self.message_post(body=f"{title}: {message}")
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_process_patient_ocr(self):
        self.ensure_one()
        result = self.dni_ocr_process_images(
            self.patient_ocr_front_image,
            self.patient_ocr_back_image,
            self.patient_ocr_front_filename,
            self.patient_ocr_back_filename,
        )
        self._ocr_apply_patient_result(result)
        if result['state'] == 'processed':
            message = _('DNI detectado: %s') % result['dni_number']
            msg_type = 'success'
        else:
            parts = []
            if result.get('full_name'):
                parts.append(_('Nombre: %s') % result['full_name'])
            if result.get('birth_date'):
                parts.append(_('Nacimiento: %s') % result['birth_date'])
            parts.append(_('DNI no detectado. Escríbalo y pulse «Confirmar DNI».'))
            message = ' · '.join(parts)
            msg_type = 'warning'
        return self._ocr_reload_form_action(_('OCR paciente'), message, msg_type)

    def action_confirm_patient_dni(self):
        self.ensure_one()
        normalized = self._normalize_id_string(self.dni)
        if not normalized:
            raise ValidationError(
                _('Indique un DNI/NIE válido en el campo DNI antes de confirmar.')
            )
        self.write({'dni': normalized, 'patient_ocr_state': 'processed'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _validate_current_step(self):
        self.ensure_one()
        if self.state == 'draft':
            if not self.full_name or not self.dni:
                raise UserError(_('Nombre completo y DNI son obligatorios para continuar.'))
            if not self.fecha_nacimiento:
                raise UserError(_('La fecha de nacimiento es obligatoria para crear el residente.'))
            for guardian_line in self.guardian_ids:
                if guardian_line._has_data_without_identity():
                    raise UserError(
                        _('Cada tutor con datos debe tener nombre o contacto existente.')
                    )

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
        for rec in self:
            if rec.state != 'economy':
                raise UserError(_('Solo se puede completar la admisión desde el paso Economía.'))
            rec._validate_current_step()
            rec._close_admission()
        return True

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

    def _get_patient_category(self):
        category = self.env['res.partner.category'].search([('name', '=', 'Paciente')], limit=1)
        if not category:
            category = self.env['res.partner.category'].create({'name': 'Paciente'})
        return category

    def _get_family_category(self):
        category = self.env['res.partner.category'].search([('name', '=', 'Familia')], limit=1)
        if not category:
            category = self.env['res.partner.category'].create({'name': 'Familia'})
        return category

    def _resolve_patient_partner(self):
        self.ensure_one()
        patient_category = self._get_patient_category()
        if self.patient_partner_id:
            partner = self.patient_partner_id
            partner_vals = {}
            if self.full_name and partner.name != self.full_name:
                partner_vals['name'] = self.full_name
            if self.dni and partner.vat != self.dni:
                partner_vals['vat'] = self.dni
            if self.phone:
                partner_vals['phone'] = self.phone
            if self.email_contact:
                partner_vals['email'] = self.email_contact
            if patient_category not in partner.category_id:
                partner_vals['category_id'] = [(4, patient_category.id)]
            if partner_vals:
                partner.write(partner_vals)
            return partner

        return self.env['res.partner'].create({
            'name': self.full_name,
            'vat': self.dni,
            'phone': self.phone or '',
            'email': self.email_contact or '',
            'category_id': [(4, patient_category.id)],
        })

    def _resolve_guardian_partner(self, patient_partner, guardian_line):
        family_category = self._get_family_category()
        partner = guardian_line.partner_id

        if not partner and guardian_line.dni:
            partner = self.env['res.partner'].search([('vat', '=', guardian_line.dni)], limit=1)
        if not partner and guardian_line.name:
            partner = self.env['res.partner'].search([
                ('name', '=', guardian_line.name),
                ('parent_id', '=', patient_partner.id),
            ], limit=1)

        partner_vals = {
            'name': guardian_line.name,
            'phone': guardian_line.phone or '',
            'email': guardian_line.email or '',
            'street': guardian_line.street or False,
            'city': guardian_line.city or False,
            'zip': guardian_line.zip or False,
            'country_id': guardian_line.country_id.id if guardian_line.country_id else False,
            'type': 'contact',
        }

        if partner:
            write_vals = {k: v for k, v in partner_vals.items() if v}
            if family_category not in partner.category_id:
                write_vals['category_id'] = [(4, family_category.id)]
            if not partner.parent_id:
                partner.write({'parent_id': patient_partner.id})
            partner.write(write_vals)
            if guardian_line.dni:
                partner.write({'vat': guardian_line.dni})
        else:
            partner_vals['category_id'] = [(4, family_category.id)]
            partner = self.env['res.partner'].create(partner_vals)
            partner.write({'parent_id': patient_partner.id})
            if guardian_line.dni:
                partner.write({'vat': guardian_line.dni})

        if guardian_line.is_payer and guardian_line.bank_acc_number:
            existing_bank = partner.bank_ids.filtered(
                lambda b: b.acc_number == guardian_line.bank_acc_number
            )
            if not existing_bank:
                self.env['res.partner.bank'].create({
                    'partner_id': partner.id,
                    'acc_number': guardian_line.bank_acc_number,
                })

        if guardian_line.is_payer:
            link_domain = [
                ('patient_id', '=', patient_partner.id),
                ('payer_id', '=', partner.id),
                ('company_id', '=', self.company_id.id),
            ]
            link = self.env['patient.wallet.family.link'].search(link_domain, limit=1)
            link_vals = {
                'patient_id': patient_partner.id,
                'payer_id': partner.id,
                'company_id': self.company_id.id,
                'relationship': guardian_line.relationship or '',
                'active': True,
            }
            if link:
                link.write({'relationship': guardian_line.relationship or link.relationship})
            else:
                self.env['patient.wallet.family.link'].create(link_vals)

        if 'dni.ocr.capture' in self.env and guardian_line.ocr_front_image and guardian_line.ocr_back_image:
            self.env['dni.ocr.capture'].create({
                'name': _('DNI tutor — %s') % guardian_line.name,
                'partner_id': partner.id,
                'front_image': guardian_line.ocr_front_image,
                'front_filename': guardian_line.ocr_front_filename or 'dni_anverso.jpg',
                'back_image': guardian_line.ocr_back_image,
                'back_filename': guardian_line.ocr_back_filename or 'dni_reverso.jpg',
                'dni_number': guardian_line.dni or False,
                'state': 'processed' if guardian_line.dni else 'review',
            })

        guardian_line.created_partner_id = partner.id
        return partner

    def _create_resident(self):
        self.ensure_one()
        patient_partner = self._resolve_patient_partner()

        existing_resident = self.env['cs.resident'].search([
            ('partner_id', '=', patient_partner.id),
        ], limit=1)

        if existing_resident:
            resident = existing_resident
            resident.write({
                'name': self.full_name,
                'dni': self.dni,
                'fecha_nacimiento': self.fecha_nacimiento,
                'phone': self.phone or '',
                'state': 'activo',
            })
        else:
            resident = self.env['cs.resident'].create({
                'name': self.full_name,
                'dni': self.dni,
                'fecha_nacimiento': self.fecha_nacimiento,
                'phone': self.phone or '',
                'partner_id': patient_partner.id,
                'state': 'activo',
            })

        for guardian_line in self.guardian_ids:
            if guardian_line._is_meaningful_guardian():
                self._resolve_guardian_partner(patient_partner, guardian_line)

        if self.patient_ocr_front_image and self.patient_ocr_back_image and 'dni.ocr.capture' in self.env:
            self.env['dni.ocr.capture'].create({
                'name': _('DNI paciente — %s') % self.full_name,
                'partner_id': patient_partner.id,
                'front_image': self.patient_ocr_front_image,
                'front_filename': self.patient_ocr_front_filename or 'dni_anverso.jpg',
                'back_image': self.patient_ocr_back_image,
                'back_filename': self.patient_ocr_back_filename or 'dni_reverso.jpg',
                'dni_number': self.dni or False,
                'state': 'processed' if self.dni else 'review',
            })

        self.resident_id = resident.id
        self.patient_partner_id = patient_partner.id

    def _apply_location(self):
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
