from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


def _is_restricted(env):
    user = env.user
    return (
        user._is_internal()
        and not user._is_superuser()
        and not user.has_group('sales_team.group_sale_manager')
    )


class ResCompany(models.Model):
    _inherit = 'res.company'

    _salesman_max_discount_range = models.Constraint(
        'CHECK(salesman_max_discount >= 0 AND salesman_max_discount <= 100)',
        "The salesman max discount must be between 0 and 100%.",
    )

    salesman_max_discount = fields.Float(string="Salesman Max Discount", default=5.0)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    salesman_max_discount = fields.Float(related='company_id.salesman_max_discount', readonly=False)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_salesman_max_discount(self):
        self.ensure_one()
        cap = self.company_id.salesman_max_discount
        if getattr(self, 'reward_id', False):
            return 100.0
        if self.combo_item_id:
            return max(cap, self._get_linked_line().discount)
        if not (
            self.order_id.pricelist_id
            and self.env['product.pricelist.item']._is_discount_feature_enabled()
            and self.pricelist_item_id._show_discount()
        ):
            return cap
        line = self.with_company(self.company_id)
        base_price = line._get_pricelist_price_before_discount()
        if not base_price:
            return cap
        return max(cap, (base_price - line._get_pricelist_price()) / base_price * 100)

    @api.constrains('discount')
    def _check_salesman_max_discount(self):
        if not _is_restricted(self.env):
            return
        digits = self.env['decimal.precision'].precision_get('Discount')
        for line in self:
            allowed = line._get_salesman_max_discount()
            if float_compare(line.discount, allowed, precision_digits=digits) > 0:
                raise ValidationError(self.env._(
                    "Discount too high on \"%(product)s\": the most you can give is %(max)s%%. Ask a Sales Manager.",
                    max=f"{round(allowed, digits):g}", product=line.product_id.display_name or line.name,
                ))

    def write(self, vals):
        if 'product_uom_qty' in vals and _is_restricted(self.env):
            for line in self:
                if (
                    line.product_id
                    and line.product_id == line.company_id.sale_discount_product_id
                    and float_compare(
                        vals['product_uom_qty'], line.product_uom_qty,
                        precision_rounding=line.product_uom_id.rounding,
                    ) > 0
                ):
                    raise ValidationError(self.env._(
                        "You can't increase the quantity of a discount line. Ask a Sales Manager."
                    ))
        return super().write(vals)


class SaleOrderDiscount(models.TransientModel):
    _inherit = 'sale.order.discount'

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields, attributes)
        selection = res.get('discount_type', {}).get('selection')
        if selection and _is_restricted(self.env):
            res['discount_type']['selection'] = [s for s in selection if s[0] != 'amount']
        return res

    @api.constrains('discount_type', 'discount_percentage')
    def _check_salesman_max_discount(self):
        if not _is_restricted(self.env):
            return
        for wizard in self:
            cap = wizard.sale_order_id.company_id.salesman_max_discount
            if wizard.discount_type == 'amount':
                raise ValidationError(self.env._("You can't give a fixed amount discount. Ask a Sales Manager."))
            if float_compare(wizard.discount_percentage, cap / 100, precision_digits=6) > 0:
                raise ValidationError(self.env._(
                    "Discount too high: the most you can give is %(max)s%%. Ask a Sales Manager.", max=f"{cap:g}",
                ))
