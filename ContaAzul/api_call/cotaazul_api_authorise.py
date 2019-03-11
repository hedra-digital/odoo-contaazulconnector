from odoo import http, tools, _
from odoo.http import request
import requests
import json
from odoo.exceptions import ValidationError
from base64 import b64encode


class ReturnAuthoriseUrl(http.Controller):

    @http.route('/authorise/contaazul', type='http', auth="user", methods=['GET', 'POST'], website=True, csrf=True)
    def authorise_contaazul(self, **kwargs):
        contaazul_url = 'https://api.contaazul.com/auth/authorize?redirect_uri=%s&client_id=%s&scope=sales&state%s=' % (
                         request.env.user.company_id.contaazul_client_callback_url,
                         request.env.user.company_id.contaazul_client_id,
                         request.csrf_token())
        return request.redirect(contaazul_url)

    @http.route('/get/access_token', type='http', auth='user', methods=['GET', 'POST'], website=True)
    def get_access_token(self, **kwargs):
        client_id_secret_string = bytes("%s:%s" %
                                        (request.env.user.company_id.contaazul_client_id,
                                         request.env.user.company_id.contaazul_client_secret_key),
                                        'utf-8')
        client_id_secret = b64encode(client_id_secret_string).decode("ascii")
        headers = {'Authorization': 'Basic %s' % client_id_secret,
                   'Content-Type': 'application/json'
                   }

        get_access_token_url = 'https://api.contaazul.com/oauth2/token'
        data = {
            'grant_type': 'authorization_code',
            'redirect_uri': request.env.user.company_id.contaazul_client_callback_url,
            'code': kwargs.get('code')
        }
        get_data = requests.post(get_access_token_url, headers=headers, data=json.dumps(data))
        redirect_url_company = "/web#id=%s&action=%s&model=res.company&view_type=form" % (request.env.user.company_id.id,request.env.ref('base.action_res_company_form').id)
        if get_data.status_code == 200:
            access_credentials = json.loads(get_data.text)
            request.env.user.company_id.write({
                'contazul_access_token': access_credentials.get('access_token'),
                'contazul_refresh_token': access_credentials.get('refresh_token'),
                'contazul_expires_in': access_credentials.get('expires_in'),
                'contazul_authorised_state': 'authorise',
            })
        else:
            return request.redirect(redirect_url_company)

        return request.redirect(redirect_url_company)
