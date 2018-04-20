# Copyright (c) 2013, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import today, add_months, cint, getdate
from functools import partial
from operator import neg
from gwi_customization.microfinance.utils.fp import compose, join
from gwi_customization.microfinance.api.loan import get_outstanding_principal
from gwi_customization.microfinance.api.interest import get_current_interest


def _set_filter(filters, fieldname):
    def fn(conds):
        if filters.get(fieldname):
            return conds + [
                "loan.{field} = '{value}'".format(
                    field=fieldname, value=filters.get(fieldname)
                )
            ]
        return conds
    return fn


def _result_to_data(row):
    return row[:-1] + (
        get_outstanding_principal(row[1]),
        get_current_interest(row[1], today()),
    )


def _display_filter(display):
    npa_duration = frappe.get_value(
        'Microfinance Loan Settings', None, 'npa_duration'
    )
    npa_date = compose(
        getdate, partial(add_months, today()), neg, cint
    )(npa_duration)

    def fn(row):
        if display == 'NPA Only':
            return row[-1] < npa_date and row[3] < npa_date
        if display == 'Existing Loans':
            return row[2] in ['Not Started', 'In Progress']
        return True
    return fn


def execute(filters=None):
    columns = [
        _("Customer") + ":Link/Customer:180",
        _("Loan No") + ":Link/Microfinance Loan:90",
        _("Status") + "::90",
        _("Last Payment Date") + ":Date:90",
        _("Last Paid Interest") + "::90",
        _("Outstanding") + ":Currency/currency:90",
        _("Curent Interest") + ":Currency/currency:90",
    ]

    conds = compose(
        _set_filter(filters, 'name'),
        _set_filter(filters, 'customer'),
        _set_filter(filters, 'loan_plan'),
    )(["loan.disbursement_status != 'Sanctioned'"])

    result = frappe.db.sql(
        """
            SELECT
                loan.customer,
                loan.name,
                loan.recovery_status,
                max(recovery.posting_date),
                interest.period,
                loan.posting_date
            FROM `tabMicrofinance Loan` AS loan
            LEFT JOIN `tabMicrofinance Recovery` AS recovery
                ON recovery.docstatus = 1
                AND recovery.loan = loan.name
            LEFT JOIN `tabMicrofinance Loan Interest` AS interest
                ON interest.docstatus = 1
                AND interest.loan = loan.name
                AND interest.billed_amount = interest.paid_amount
            WHERE loan.docstatus = 1
            AND {conds}
            GROUP BY loan.name
        """.format(
            conds=join(" AND ")(conds)
        )
    )
    data = compose(
        partial(map, _result_to_data),
        partial(filter, _display_filter(filters.get('display')))
    )(result)
    return columns, data