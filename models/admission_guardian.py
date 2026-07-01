from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CsAdmissionGuardian(models.Model):
    _name = "cs.admission.guardian"
    _description = "Tutor / familiar en admisión"
    _inherit = ["cs.family.relationship.mixin", "dni.ocr.engine"]
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    admission_id = fields.Many2one(
        "cs.admission.process",
        string="Admisión",
        required=True,
        ondelete="cascade",
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contacto existente",
        help="Seleccione un contacto ya registrado o rellene los datos manualmente.",
    )
    name = fields.Char(
        string="Nombre y apellidos",
        required=True,
        default=lambda self: _("Nuevo tutor"),
    )
    dni = fields.Char(string="DNI / NIE")
    street = fields.Char(string="Dirección")
    city = fields.Char(string="Ciudad")
    zip = fields.Char(string="CP")
    country_id = fields.Many2one(
        "res.country",
        string="País",
        default=lambda self: self.env.ref("base.es", raise_if_not_found=False),
    )
    phone = fields.Char(string="Teléfono")
    email = fields.Char(string="Email")
    relationship = fields.Char(string="Parentesco")
    is_payer = fields.Boolean(string="Es pagador")
    bank_acc_number = fields.Char(string="IBAN / Nº cuenta")
    ocr_front_image = fields.Binary(string="DNI anverso", attachment=True)
    ocr_front_filename = fields.Char(string="Nombre anverso")
    ocr_back_image = fields.Binary(string="DNI reverso", attachment=True)
    ocr_back_filename = fields.Char(string="Nombre reverso")
    ocr_state = fields.Selection(
        [
            ("none", "Sin OCR"),
            ("processed", "Procesado"),
            ("review", "Revisión"),
        ],
        string="Estado OCR",
        default="none",
        readonly=True,
    )
    ocr_front_text = fields.Text(string="Texto OCR anverso", readonly=True)
    ocr_back_text = fields.Text(string="Texto OCR reverso", readonly=True)
    ocr_show_review_text = fields.Boolean(
        string="Texto OCR (revisión)",
        default=False,
        help="Mostrar el texto bruto del OCR para revisión manual.",
    )
    created_partner_id = fields.Many2one(
        "res.partner",
        string="Contacto creado",
        readonly=True,
        copy=False,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "name" in fields_list and not res.get("name"):
            res["name"] = _("Nuevo tutor")
        return res

    def _guardian_name_placeholder(self):
        return _("Nuevo tutor")

    def _is_meaningful_guardian(self):
        self.ensure_one()
        name = (self.name or "").strip()
        if name and name != self._guardian_name_placeholder():
            return True
        if self.partner_id:
            return True
        return False

    def _has_data_without_identity(self):
        self.ensure_one()
        if self._is_meaningful_guardian():
            return False
        return bool(
            self.dni
            or self.phone
            or self.email
            or self.street
            or self.city
            or self.is_payer
            or self.bank_acc_number
        )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if not self.partner_id:
            return
        partner = self.partner_id
        self.name = partner.name or self.name
        self.dni = partner.vat or partner.ref or self.dni
        self.street = partner.street or self.street
        self.city = partner.city or self.city
        self.zip = partner.zip or self.zip
        self.country_id = partner.country_id or self.country_id
        self.phone = partner.phone or partner.mobile or self.phone
        self.email = partner.email or self.email
        bank = partner.bank_ids[:1]
        if bank:
            self.bank_acc_number = bank.acc_number or self.bank_acc_number

    def _action_open_ocr_dialog(self):
        self.ensure_one()
        view = self.env.ref("cs_admission.view_cs_admission_guardian_form_ocr", raise_if_not_found=False)
        return {
            "type": "ir.actions.act_window",
            "name": _("DNI tutor — %s") % (self.name or _("Nuevo tutor")),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(view.id if view else False, "form")],
            "target": "new",
        }

    def action_process_ocr(self):
        self.ensure_one()
        if not self.id:
            raise UserError(
                _(
                    "Guarde la admisión antes de adjuntar o procesar el DNI del tutor "
                    "(icono del disco arriba a la izquierda)."
                )
            )
        if not self.ocr_front_image or not self.ocr_back_image:
            return self._action_open_ocr_dialog()
        result = self.dni_ocr_process_images(
            self.ocr_front_image,
            self.ocr_back_image,
            self.ocr_front_filename,
            self.ocr_back_filename,
        )
        vals = {
            "ocr_state": result["state"],
            "ocr_front_text": result.get("front_text") or "",
            "ocr_back_text": result.get("back_text") or "",
        }
        if result.get("dni_number"):
            vals["dni"] = result["dni_number"]
        if result.get("full_name"):
            vals["name"] = result["full_name"]
        if result.get("street"):
            vals["street"] = result["street"]
        if result.get("city"):
            vals["city"] = result["city"]
        if result.get("country"):
            country = self._country_name_to_record(result["country"])
            if country:
                vals["country_id"] = country.id
        self.write(vals)
        admission = self.admission_id
        if admission:
            admission.message_post(
                body=_("OCR tutor %s: %s") % (self.name, result.get("dni_number") or _("revisión"))
            )
            return {
                "type": "ir.actions.act_window",
                "res_model": "cs.admission.process",
                "res_id": admission.id,
                "view_mode": "form",
                "target": "current",
            }
        return True

    def action_confirm_dni(self):
        for rec in self:
            normalized = rec._normalize_id_string(rec.dni)
            if not normalized:
                raise ValidationError(
                    _("Indique un DNI/NIE válido en el campo DNI antes de confirmar.")
                )
            rec.write({"dni": normalized, "ocr_state": "processed"})
        return True
