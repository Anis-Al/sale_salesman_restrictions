import { onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { AccountPaymentField } from "@account/components/account_payment_field/account_payment_field";

patch(AccountPaymentField.prototype, {
    setup() {
        super.setup(...arguments);
        onWillStart(async () => {
            this.canUnreconcile = await user.hasGroup("sales_team.group_sale_manager");
        });
    },

    onInfoClick(ev, line) {
        super.onInfoClick(ev, { ...line, canUnreconcile: this.canUnreconcile });
    },
});
