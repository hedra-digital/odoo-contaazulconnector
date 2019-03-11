from odoo import models, api
import requests
import logging
from base64 import b64encode
import json


class ContazulApiCall(models.Model):
    _name = 'contazul.api.call'
    _auto = False
    log_access = False

    # refresh token
    @api.model
    def refresh_contazul(self, company_id):
        company_id = self.env['res.company'].browse(company_id)
        client_id_secret_string = bytes("%s:%s" % (company_id.contaazul_client_id,
                                                   company_id.contaazul_client_secret_key), 'utf-8')
        client_id_secret = b64encode(client_id_secret_string).decode("ascii")
        headers = {'Authorization': 'Basic %s' % client_id_secret,
                   'Content-Type': 'application/json'
                   }
        get_access_token_url = 'https://api.contaazul.com/oauth2/token'
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': company_id.contazul_refresh_token
        }
        get_data = requests.post(get_access_token_url, headers=headers, data=json.dumps(data))

        access_credentials = json.loads(get_data.text)
        # 200 ok
        if get_data.status_code == 200:
            company_id.write({
                'contazul_access_token': access_credentials.get('access_token'),
                'contazul_refresh_token': access_credentials.get('refresh_token'),
                'contazul_expires_in': access_credentials.get('expires_in'),
                'contazul_authorised_state': 'authorise',
            })
            return get_data.status_code, True
        else:
            status_code = str(get_data.status_code) or ''
            error_message = status_code + '\n' + (access_credentials.get('error_description') or '')
            return get_data.status_code, error_message

    def synchronize_contazul_api(self, values, company_id):
        # get company id
        company_id = self.env['res.company'].browse(company_id) or self.env.user.company_id.id
        headers = {'Authorization': 'Bearer %s' % company_id.contazul_access_token,
                   'Content-Type': 'application/json'
                   }
        get_access_token_url = self.env['ir.config_parameter'].sudo().get_param('ks_api_link') or ''
        get_access_token_url += self._context.get('api_hit') or ''
        try:
            installments = ''
            # for customer
            if self._context.get('api_type') and self._context.get('api_type') == 'customer':
                data = self.get_customer_data(values)
            elif self._context.get('api_type') and self._context.get('api_type') == 'products':
                # for products
                data = self.get_product_data(values)
                # for service
            elif self._context.get('api_type') and self._context.get('api_type') == 'service':
                data = self.get_services_data(values)
                # for invoice
            elif self._context.get('api_type') and self._context.get('api_type') == 'invoice':
                data = self.get_invoice_data(values, company_id.id)
            if values.get('contaazul_id') and self._context.get('api_type') == 'invoice':
                get_data, installments = self.complete_installments(headers, values)
            elif values.get('contaazul_id'):
                get_access_token_url += '/%s' % (values.get('contaazul_id'))
                get_data = requests.put(get_access_token_url, headers=headers, data=json.dumps(data))
            else:
                get_data = requests.post(get_access_token_url, headers=headers, data=json.dumps(data))
            if get_data.text:
                response_data = json.loads(get_data.text)
            else:
                response_data = dict(error_description="Something went wrong")
        except Exception:
            logging.info('fail')
            return 500, dict(error_description='Something went wrong')
        return get_data.status_code, response_data

    # synchronize product
    @api.model
    def synchronize_contazul(self, values, company_id):
        response_code, response_status = self.synchronize_contazul_api(values, company_id)
        if response_code in [201, 200]:
                return True, response_status
        elif response_code == 401:
            code, message = self.refresh_contazul(company_id)
            if code == 200:
                # ok response
                response_code, response_status = self.synchronize_contazul_api(values, company_id)
                if response_code == 201:
                    return True, response_status
        return False, response_status

    def get_customer_data(self, values):
        data = {
            "name": values.get('name'),
            "company_name": self.env.user.company_id.name,
            "email": values.get('email') or '',
            "business_phone": values.get('phone') or '',
            "mobile_phone": values.get('mobile') or '',
            "person_type": "NATURAL",
            "notes": values.get('comment') or '',
            "contacts": [{"name": i.name or '',
                          "business_phone": i.phone or '',
                          "email": i.email or '',
                          "job_title": i.function or '',
                          } for i in self.env['res.partner'].browse(values.get('child_ids'))],
            "address": {
                "zip_code": values.get('zip') or '',
                "street": values.get('street') or '',
                "complement": values.get('street2') or '',
            },
        }
        return data

    def get_product_data(self, values):
        data = {
            "name": values.get('name'),
            "value": values.get('list_price'),
            "cost": values.get('standard_price'),
            "barcode": values.get('barcode'),
            "net_weight": values.get('weight'),
            "code": values.get('default_code') or '',
            "available_stock": values.get('qty_available') or 0,
            "ncm": self.env['product.fiscal.classification'].browse(values.get('fiscal_classification_id')[0]).code
            if values.get('fiscal_classification_id') else ''
        }
        return data

    def get_invoice_data(self, values, company_id):
        data = {
            "status": "COMMITTED",
            "emission": self.get_contazul_format_data(values.get('create_date')) or '',
            "products": [{"description": i.product_id.name,
                          "quantity": i.quantity,
                          "product_id": i.product_id.with_context
                          (force_company=company_id).contaazul_id,
                          "value": i.price_unit} for i in self.env['account.invoice.line'].browse(
                values.get('invoice_line_ids')) if i.product_id.type != 'service'],
            "services": [{"description": i.product_id.name,
                          "quantity": i.quantity,
                          "service_id": i.product_id.with_context(force_company=company_id).contaazul_id,
                          "value": i.price_unit} for i in self.env['account.invoice.line'].browse(
                values.get('invoice_line_ids')) if i.product_id.type == 'service'],
            "customer_id": self.env['res.partner'].browse(values.get('partner_id')[0]).with_context
                           (force_company=company_id).contaazul_id or '',
            "discount": {
                            "measure_unit": "VALUE",
                            "rate": values.get('total_desconto') or '',
                          },
            "payment": {"type": "CASH",
                        "installments": [{"number": key,
                                          "value": i.amount,
                                          "due_date": self.get_contazul_format_data(i.create_date) or '',
                                          "status": "PENDING",
                                          } for key, i in enumerate(
                            self.env['account.payment'].browse(values.get('payment_ids')), 1)
                                         ]
                        },
            "shipping_cost": (values.get('total_frete') or 0) + (values.get('total_seguro') or 0) +
                             (values.get('total_despesas') or 0),
            "notes": (values.get('origin') or '') + ' ' + (str(values.get('freight_responsibility')) if
                                                     values.get('freight_responsibility') else '')
        }
        return data

    def get_services_data(self, values):
        data = {
            "name": values.get('name'),
            "value": values.get('list_price'),
            "cost": values.get('standard_price')
        }
        return data

    def get_contazul_format_data(self, convert_date):
        converted_date = convert_date.strftime("%Y-%m-%dT%H:%M:%S.")
        converted_date += convert_date.strftime("%f")[:3] + 'Z'
        return converted_date

    def compare_list(self, list1, list2):
        for element in list1:
            if element in list2:
                return True
        return False

    def check_product_update(self, values):
        return self.compare_list(values, ['name', 'list_price', 'standard_price',
                                          'barcode', 'default_code', 'qty_available', 'fiscal_classification_id'])

    def check_customer_update(self, values):
        return self.compare_list(values, ['name', 'email', 'phone', 'company_name',
                                          'mobile', 'comment', 'child_ids', 'zip', 'street', 'street2'])

    def check_service_update(self, values):
        return self.compare_list(values, ['name', 'list_price', 'standard_price'])

    def get_compare_lists(self, list1, list2):
        diffrent_elements = []
        for element in list1:
            if not element in list2:
                diffrent_elements.append(element)
        return diffrent_elements

    def synchronise_all_invoices(self, company_id):
        company_id = self.env['res.company'].browse(company_id)
        headers = {'Authorization': 'Bearer %s' % company_id.contazul_access_token,
                   'Content-Type': 'application/json'
                   }
        get_access_token_url = self.env['ir.config_parameter'].sudo().get_param('ks_api_link') or ''
        get_access_token_url += '/v1/sales'
        try:
            get_data = requests.get(get_access_token_url, headers=headers)
            if get_data.status_code == 401:
                self.refresh_contazul(company_id.id)
                headers = {'Authorization': 'Bearer %s' % company_id.contazul_access_token,
                           'Content-Type': 'application/json'
                           }
                get_data = requests.get(get_access_token_url, headers=headers)
            if get_data.status_code == 200:
                conta_invoices = json.loads(get_data.text)
                conta_invoice_ids = [i.get('id') for i in conta_invoices]
                all_invoice_contazul = self.env['account.invoice'].with_context(force_company=company_id.id).search([
                                                                        ('type', '=', 'out_invoice'),
                                                                           ('company_id', '=', company_id.id)])
                contaazul_ids = all_invoice_contazul.\
                    filtered(lambda x: x.contaazul_id != '' and x.contaazul_id != False).mapped('contaazul_id')
                contaazul_ids = self.get_compare_lists(conta_invoice_ids, contaazul_ids)
                logging.info(len(contaazul_ids))
                for contazul_id in contaazul_ids:
                    logging.info('invoice found%s' % (contazul_id))
                    data = [i for i in conta_invoices if i.get('id') == contazul_id].pop()
                    if data.get('customer_id'):
                        customer_id = self.env['res.partner'].with_context(force_company=company_id.id).search(
                            [('contaazul_id', '=', data.get('customer_id'))]).id
                        if not customer_id:
                            customer_id = self.get_customer_id(data.get('customer'), company_id.id)
                        url = get_access_token_url + '/' + contazul_id + '/items'
                        product_data = requests.get(url, headers=headers)
                        if product_data.status_code == 401:
                            self.refresh_contazul(company_id.id)
                            headers = {'Authorization': 'Bearer %s' % company_id.contazul_access_token,
                                       'Content-Type': 'application/json'
                                       }
                            product_data = requests.get(url, headers=headers)
                        if product_data.status_code == 200:
                            product_lines = json.loads(product_data.text)
                            sale_order_line = []
                            for product in product_lines:
                                product_id = self.validate_contazul_product_id(product.get('item'),
                                                                               product.get('itemType'),
                                                                               (company_id.id))

                                sale_order_line.append((0, 0, {

                                    'product_id': product_id.id,
                                    'name': product.get('description') or product_id.name,
                                    'product_uom_qty': product.get('quantity'),
                                    'price_unit': product.get('value')/product.get('quantity'),
                                    'price_subtotal': product.get('value'),
                                    'discount':data.get('discount').get('rate') if data.get('discount').get('measure_unit') == 'PERCENT' else 0,
                                    'tax_id': False,
                                    'company_id': company_id.id,
                                }))
                            sale_order = self.env['sale.order'].create({
                                'partner_id': customer_id,
                                'order_line': sale_order_line,
                                'company_id': company_id.id,
                                'warehouse_id': self.env['stock.warehouse'].with_context(force_company=company_id).search
                                ([('company_id', '=', company_id.id)], limit=1).id
                            })
                            sale_order.total_frete = data.get('shipping_cost')
                            sale_order._onchange_despesas_frete_seguro()
                            sale_order._amount_all()
                            sale_order.action_confirm()
                            invoice_id = self.validate_sale_invoice(sale_order, company_id.id)
                            logging.info(invoice_id.number)
                            invoice_id.write({
                                'contaazul_id': contazul_id,
                            })
                            installment = ''
                            for installments in data.get('payment').get('installments'):

                                if installments.get('status') == 'ACQUITTED':
                                    self.pay_sale_invoice(invoice_id, installments)

                                else:
                                    installment += str(installments.get('number')) + ','
                            invoice_id.write({
                                'contaazul_id': contazul_id,
                                'synch_with_contaazul': True if invoice_id.state == 'paid' else False,
                                'installments_ids': installment,
                            })

        except Exception as e:
            logging.info("data error")

    def get_customer_id(self, data, company_id):
        return self.env['res.partner'].with_context(force_company=company_id).create({
            'name': data.get('name'),
            'email': data.get('email'),
            'contaazul_id': data.get('id'),
            'customer': True,
            'synch_with_contaazul': True,
            'company_id': company_id
        }).id

    def validate_contazul_product_id(self, contazul_id, item_type, company_id):
        product_id = self.env['product.product'].with_context(force_company=company_id).search([('contaazul_id', '=', contazul_id.get('id'))], limit=1)
        if not product_id:
            product_id = self.env['product.product'].with_context(force_company=company_id).create({
                'name': contazul_id.get('name'),
                'contaazul_id': contazul_id.get('id'),
                'list_price': contazul_id.get('value'),
                'standard_price': contazul_id.get('cost'),
                'company_id': company_id,
                'type': 'service' if item_type and item_type == 'SERVICE' else 'product',
                'synch_with_contaazul': True
            })
        return product_id

    def validate_sale_invoice(self, sale_order, company_id):
        create_invoice = self.env['sale.advance.payment.inv'].with_context(force_company=sale_order.company_id.id).create({
            'count': 1,
            'advance_payment_method': 'delivered'
        })
        create_invoice = create_invoice.with_context(active_id=sale_order.id,
                                                     active_ids=sale_order.ids,
                                                     active_model='sale.order',
                                                     force_company=sale_order.company_id.id)
        create_invoice.create_invoices()
        invoice_id = sale_order.invoice_ids[0]
        invoice_id.journal_id = self.env['account.journal'].sudo().search([('company_id', '=', company_id),
                                                   ('type', '=', 'sale')], limit=1)
        invoice_id.with_context(force_company=sale_order.company_id.id).action_invoice_open()
        return invoice_id

    def pay_sale_invoice(self, invoice_id, installment):
        method = invoice_id.journal_id.inbound_payment_method_ids
        values = {'amount': installment.get('value') or 0,
                  'currency_id': invoice_id.currency_id.id,
                  'journal_id': self.env['account.journal'].search(
                      [('type', '=', 'bank'), ('company_id', '=', invoice_id.company_id.id)], limit=1, order='id').id,
                  'payment_date': invoice_id.create_date,
                  'payment_method_id': method.id and method[0].id or False,
                  'payment_type': "inbound",
                  'invoice_ids': [(6, 0, invoice_id.ids)],
                  'partner_type': 'customer',
                  'partner_id': invoice_id.partner_id.id,
                  'communication': invoice_id.number,
                  }
        invoice_payment = invoice_id.payment_ids.create(values)
        invoice_payment.action_validate_invoice_payment()
        logging.info("installment done")
        return invoice_id

    def do_shipping(self, sale_order):
        picking_ids = self.env['stock.immediate.transfer'].create({
            'pick_ids': [(6, 0, sale_order.picking_ids.ids)]
        })
        picking_ids = picking_ids.with_context(active_id=sale_order.id,
                                               active_ids=sale_order.ids,
                                               active_model='sale.order')
        picking_ids.process()

    def complete_installments(self, headers, values):
        installment_ids = values.get('installments_ids')
        installment_remaining = installment_ids
        installment_no = installment_ids.split(',')[:-1]
        installment_no = [int(i) for i in installment_no]
        get_data = {}
        get_access_token_url = self.env['ir.config_parameter'].sudo().get_param('ks_api_link') or ''
        data = {
            'status': 'ACQUITTED'
        }

        if installment_no:
            for installment in installment_no:
                api_url = get_access_token_url + '/v1/sales/%s/installments/%d' % (values.get('contaazul_id'), installment)
                get_data = requests.put(api_url, headers=headers, data=json.dumps(data))
                logging.info(get_data.status_code)
                if get_data.status_code == 200:
                    installment_remaining.replace((str(installment_no)+','), '')
        else:
            api_url = get_access_token_url + '/v1/sales/%s/installments/%d' % (values.get('contaazul_id'), 1)
            get_data = requests.put(api_url, headers=headers, data=json.dumps(data))
        return get_data, installment_remaining

    def get_invoice_status(self, invoice):
        headers = {'Authorization': 'Bearer %s' % invoice.company_id.contazul_access_token,
                   'Content-Type': 'application/json'
                   }
        get_access_token_url = self.env['ir.config_parameter'].sudo().get_param('ks_api_link') or ''
        get_access_token_url += '/v1/sales/' + invoice.contaazul_id
        installment_ids = invoice.installments_ids.split(',')[:-1]
        installment_no = [int(i) for i in installment_ids]
        try:
            get_data = requests.get(get_access_token_url, headers=headers)
            if get_data.status_code == 401:
                self.refresh_contazul(invoice.company_id.id)
                headers = {'Authorization': 'Bearer %s' % invoice.company_id.contazul_access_token,
                           'Content-Type': 'application/json'
                           }
            if get_data.status_code == 200:
                data = json.loads(get_data.text)
                get_installments = data.get('payment').get('installments')
                contaazul_paid_installments = [i.get('number') for i in get_installments if i.get('status')=='ACQUITTED']
                for installment in installment_no:
                    if installment in contaazul_paid_installments:
                        installment_pay = [i for i in get_installments if i.get('number') == installment]
                        if installment_pay:
                            self.pay_sale_invoice(invoice, installment_pay[0])
                            installment_no = invoice.installments_ids
                            invoice.write({'installments_ids': installment_no.replace(str(installment)+',', "", 1)})

        except Exception as e:
            logging.info(invoice.number)
            logging.info("data error")
