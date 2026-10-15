# sale_salesman_restrictions

Author / maintainer: **Anis Alim**. License LGPL-3.

Restricts quotations for every user who is **not** in `sales_team.group_sale_manager`.

Status 2026-10-15: **installed on `mconfort`** and `mconfort-loyalty`, 4/4 tests green.

## Standing instructions (from the client)

1. **No inline code comments.** Anything a comment would say goes in "Code
   comments" below. Keep that section in step with the code.
2. **No `aa` prefix** in the technical name, method names, view ids or test logins.
3. Author / maintainer is **Anis Alim**.
4. User-facing text: **simple wording**, English in code, French in `i18n/fr.po`.
5. Log every change in "Change log" with the date.
6. **Git**: commits carry **no** `Co-Authored-By` line. Remote is
   `github.com/Anis-Al/sale_salesman_restrictions`, branch `main`.

## Behaviour

| Where | What non-managers get |
|---|---|
| `sale.order` form | `margin` block (margin + margin %) hidden |
| `sale.order.line` (list + line form) | `purchase_price`, `margin`, `margin_percent`, `tax_ids` hidden |
| `account.move` invoice lines (list + line form) | `tax_ids` hidden |
| `sale.order.line.discount` | capped at **5%** (server-side constraint) |
| Discount wizard (`action_open_discount_wizard`) | `sol_discount` and `so_discount` capped at **5%**; `amount` (Fixed Amount) hidden and refused |
| Global discount lines (company discount product) | quantity can't be **increased** (server-side) |

Managers see and do everything as in standard Odoo. On invoices, accounting users
(Administrator, or Readonly / Accountant) also keep `tax_ids`.

## Files

- `models/sale.py` — line constraint, wizard constraint, wizard `fields_get` filter
- `views/sale_views.xml` — inherited views of `sale.order.form` and `account.view_move_form`, `groups` attributes only
- `tests/test_restrictions.py` — salesman vs manager, line + wizard + invoice taxes
- `i18n/fr.po` — French for the 3 error messages

## Update and test

Test on `mconfort-loyalty` first, then `mconfort`. Use `-u` once installed —
`-i` on an already-installed module loads nothing and runs **0 tests**. Write the
log to a file: piping odoo-bin output through `Select-String` in PowerShell loses it.

```powershell
& "C:\Program Files\Odoo 19.0.20260724\python\python.exe" `
  "C:\Program Files\Odoo 19.0.20260724\server\odoo-bin" `
  -c "C:\Program Files\Odoo 19.0.20260724\server\odoo.conf" `
  -d mconfort-loyalty -u sale_salesman_restrictions `
  --test-tags /sale_salesman_restrictions --stop-after-init --no-http `
  --logfile=<scratch>\test.log --log-level=test
Select-String -Path <scratch>\test.log -Pattern "ERROR|FAIL|tests when"
```

Expect `0 failed, 0 error(s) of 4 tests`. On `mconfort` the log also shows errors
that are not this module's: `ai.embedding has no table`, missing
`website_sale_default_order` / `website_snippets`, a Studio view a11y warning.

`fr_FR` is **not** active on `mconfort-loyalty` — French can only be checked live
on `mconfort`.

## Code comments

Code files carry no inline comments by request; everything a comment would say lives here.

- **`_is_restricted(env)`**: true for an internal user who is neither the superuser
  (`__system__`, crons) nor a Sales Manager. It deliberately does **not** look at
  `env.su`: Odoo 19 `_validate_fields` runs every `@api.constrains` as `sudo()`, so an
  `env.su` test would always skip the check (found by the tests, 2026-10-15).
  `env.user` is still the real user under `sudo()`. Portal/public users (website
  checkout) are not restricted; their discounts only come from pricelists/loyalty.
- **Hiding is view-level, not field-level.** `groups` on the view nodes, not on the
  Python fields. Field-level `groups` on `tax_ids` / `purchase_price` would raise
  `AccessError` for salesmen in computes (totals, taxes, margin) and in reports.
  Hidden fields still exist server-side; this is a UI restriction, not data security
  (RPC can still read them).
- **`_get_salesman_max_discount()`** — the cap is `max(5%, what the system itself put there)`:
  - loyalty reward lines (`reward_id`, free product = 100% discount) → 100%
  - combo item lines copy their parent line's discount → parent's discount allowed
  - pricelist rules shown as a discount (`_show_discount()`) → the pricelist %
    is allowed. Formula copied from core `sale.order.line._compute_discount`.
    `mconfort` has 43 percentage pricelist rules, so without this a salesman could
    not save a line priced by such a rule.
  - A salesman therefore can never go *above* the pricelist %, and never above 5%
    by hand on a line without a pricelist discount.
- **Precision**: line check uses the `Discount` decimal precision; wizard check
  compares the 0–1 fraction (`0.05` = 5%) at 6 digits.
- **Old data**: the constraint only fires when `discount` is written. 101 existing
  lines on `mconfort` are already above 5% (2026-10-15); they stay valid until a
  salesman edits their discount.
- **Wizard `fields_get` override** drops `amount` from the radio for non-managers;
  the selection labels stay translated because they come from `super()`. The
  constraint refuses `amount` anyway in case it is sent by RPC.
- **Global discount line qty** (`sale.order.line.write`): the `so_discount` wizard adds lines
  with `company.sale_discount_product_id` and a negative `price_unit`; raising their qty would
  multiply the discount past 5%. For restricted users, `write` refuses a `product_uom_qty`
  greater than the current one on those lines. Same qty or lower is fine (lower = less
  discount). `create` is untouched because the wizard creates the lines as the salesman.
- **Invoice `tax_ids`**: only `invoice_line_ids` (list + form) is touched. The Journal
  Items tab (`line_ids`) is already `groups="account.group_account_readonly"` in core.
  `groups` means "any listed group and none of the `!` ones" (`has_groups`), so "manager or not a salesman" can't be written;
  instead the field stays for `group_sale_manager`, `group_account_manager` and
  `group_account_readonly` (implied by Accountant). A billing-only user who is not a
  salesman would also lose the column — none exist on `mconfort` (2026-10-15).
  Tax totals at the bottom of the invoice stay visible.
- **View priority 50** so the xpaths run after `sale_margin`'s inherited view
  (priority 15), which is what adds `margin`, `purchase_price`, `margin_percent`.
- **Error messages** are short plain wording ("Discount too high… Ask a Sales
  Manager."). `max` is passed as `f"{x:g}"` so users read `5%`, not `5.0%`.

## Translations

`i18n/fr.po` — French only (`mconfort` has just `en_US` + `fr_FR` active). Simple
wording on purpose. If an English message in `models/sale.py` changes, its `msgid`
in `fr.po` must change to the exact same text, or the French silently falls back
to English. After editing, update with `-u sale_salesman_restrictions --i18n-overwrite`.

## Not done

- Pivot/graph measures for margin on `sale.order` are untouched.
- Global discount lines: `price_unit` is not locked, and a salesman can still add the
  discount product as a normal line by hand. The qty field is not made readonly in the view
  (the error shows on save).

## Change log

- 2026-10-15 — 19.0.1.0.0 created.
- 2026-10-15 — renamed from `aa_sale_salesman_restrictions`; no `aa` prefix in the
  technical name or method names. Old name uninstalled from `mconfort-loyalty`.
- 2026-10-15 — French translations (`i18n/fr.po`); error messages reworded simpler.
- 2026-10-15 — **installed on `mconfort`** (second odoo-bin, `-i`). 2/2 tests green.
  Checked there as a French salesman (rolled back): margin/cost/taxes hidden, wizard
  shows only the two % options, all 3 errors in French. Also installed on
  `mconfort-loyalty`.
- 2026-10-15 — this file: standing instructions, update/test commands.
- 2026-10-15 — French: dropped "Demandez à un responsable des ventes." from all 3
  messages (English unchanged). Python-error translations are cached per process
  (`odoo/tools/translate.py` `code_translations`), so the running service shows the
  new French only after `Restart-Service odoo-server-19.0` (elevated).
- 2026-10-15 — invoice lines (`account.move` form): `tax_ids` hidden for non-managers.
  Updated on `mconfort-loyalty` and `mconfort`, 3/3 tests green.
- 2026-10-15 — standing instruction 6: no `Co-Authored-By` in commits; remote noted.
- 2026-10-15 — global discount lines: salesmen can't increase their quantity. New test,
  French message. Updated on `mconfort-loyalty` and `mconfort`, 4/4 tests green.
- 2026-10-15 — discount column on sale lines was hidden for salesmen by
  `account_hide_cancel_invoicing` (not this module); fixed there (`3651883`).
