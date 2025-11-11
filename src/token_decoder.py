"""
Utilitário para decodificação de tokens Senior
"""

import json
import urllib.parse
from typing import Dict, Optional
from datetime import datetime, timedelta


class SeniorTokenDecoder:
    """Classe para decodificação e análise de tokens Senior"""

    @staticmethod
    def decode_token(encoded_token: str) -> Optional[Dict]:
        """
        Decodifica um token Senior URL-encoded

        Args:
            encoded_token (str): Token em formato URL-encoded

        Returns:
            Dict or None: Token decodificado como dicionário ou None se erro
        """
        try:
            # Decodificar URL encoding
            decoded_token = urllib.parse.unquote(encoded_token)

            # Converter JSON string para dicionário
            token_data = json.loads(decoded_token)

            return token_data

        except (json.JSONDecodeError, Exception):
            return None

    @staticmethod
    def get_token_info(token_data: Dict) -> Dict:
        """
        Extrai informações estruturadas do token

        Args:
            token_data (Dict): Token decodificado

        Returns:
            Dict: Informações estruturadas do token
        """
        if not token_data:
            return {}

        # Calcular data de expiração
        expires_in = token_data.get('expires_in', 0)
        expiration_date = datetime.now() + timedelta(seconds=expires_in)

        return {
            'version': token_data.get('version'),
            'token_type': token_data.get('token_type'),
            'scope': token_data.get('scope'),
            'auth_type': token_data.get('type'),
            'expires_in_seconds': expires_in,
            'expires_in_hours': expires_in // 3600,
            'expiration_date': expiration_date.strftime('%Y-%m-%d %H:%M:%S'),
            'user_info': {
                'username': token_data.get('username'),
                'email': token_data.get('email'),
                'full_name': token_data.get('fullName', '').replace('+', ' '),
                'tenant_name': token_data.get('tenantName'),
                'locale': token_data.get('locale')
            },
            'tokens': {
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token')
            },
            'device_id': SeniorTokenDecoder._extract_device_id(token_data.get('scope', ''))
        }

    @staticmethod
    def _extract_device_id(scope: str) -> Optional[str]:
        """Extrai o device ID do scope"""
        if 'device_' in scope:
            parts = scope.split('device_')
            if len(parts) > 1:
                return parts[1]
        return None

    @staticmethod
    def is_token_valid(token_data: Dict) -> bool:
        """
        Verifica se o token ainda é válido

        Args:
            token_data (Dict): Token decodificado

        Returns:
            bool: True se token é válido
        """
        if not token_data:
            return False

        required_fields = ['access_token', 'expires_in', 'username']
        return all(field in token_data for field in required_fields)

    @staticmethod
    def format_token_summary(token_data: Dict) -> str:
        """
        Formata um resumo do token para exibição

        Args:
            token_data (Dict): Token decodificado

        Returns:
            str: Resumo formatado do token
        """
        if not token_data:
            return "Token inválido"

        info = SeniorTokenDecoder.get_token_info(token_data)

        summary = []
        summary.append(f"Usuario: {info['user_info']['username']}")
        summary.append(f"Email: {info['user_info']['email']}")
        summary.append(f"Nome: {info['user_info']['full_name']}")
        summary.append(f"Tenant: {info['user_info']['tenant_name']}")
        summary.append(f"Expira em: {info['expires_in_hours']} horas")
        summary.append(f"Data expiracao: {info['expiration_date']}")
        summary.append(f"Access Token: {info['tokens']['access_token']}")
        summary.append(f"Refresh Token: {info['tokens']['refresh_token']}")

        return "\n".join(summary)

    @staticmethod
    def get_auth_headers(token_data: Dict) -> Dict[str, str]:
        """
        Gera headers de autenticação para usar em requisições

        Args:
            token_data (Dict): Token decodificado

        Returns:
            Dict: Headers de autenticação
        """
        if not token_data:
            return {}

        access_token = token_data.get('access_token', '')

        return {
            'Authorization': f"Bearer {access_token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    @staticmethod
    def get_auth_cookies(encoded_token: str, additional_cookies: Dict = None) -> Dict[str, str]:
        """
        Gera cookies de autenticação para usar em requisições

        Args:
            encoded_token (str): Token original URL-encoded
            additional_cookies (Dict): Cookies adicionais da sessão

        Returns:
            Dict: Cookies de autenticação
        """
        cookies = {
            'com.senior.token': encoded_token
        }

        if additional_cookies:
            cookies.update(additional_cookies)

        return cookies
