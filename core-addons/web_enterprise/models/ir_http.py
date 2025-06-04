# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import models
from odoo.http import request


class Http(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _post_logout(cls):
        super()._post_logout()
        request.future_response.set_cookie('color_scheme', max_age=0)

    def webclient_rendering_context(self):
        """ Overrides community to prevent unnecessary load_menus request """
        return {
            'session_info': self.session_info(),
        }

def session_info(self):
    # Determinar el tipo de usuario según su grupo
    if self.env.user.has_group('base.group_system'):
        warn_enterprise = 'admin'
    elif self.env.user._is_internal():
        warn_enterprise = 'user'
    else:
        warn_enterprise = False
    
    # Obtener la información original de la sesión
    result = super().session_info()
    
    # Agregar información extra al resultado
    result['warn_enterprise'] = warn_enterprise
    result['support_url'] = "https://www.odoo.com/help"
    
    # Devolver la información actualizada
    return result
