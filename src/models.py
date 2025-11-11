"""
Modelos de dados para o módulo de autenticação Senior
"""
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class AuthenticationResult:
    """
    Resultado de uma tentativa de autenticação na plataforma Senior

    Attributes:
        success (bool): Indica se a autenticação foi bem-sucedida
        senior_token (str, optional): Token principal da Senior (com.senior.token)
        cookies (Dict[str, str]): Todos os cookies retornados pela resposta
        status_code (int, optional): Código de status HTTP da resposta
        redirect_location (str, optional): URL de redirecionamento
        error_message (str, optional): Mensagem de erro, se houver
        response_headers (Dict[str, str], optional): Headers da resposta HTTP
    """
    success: bool
    cookies: Dict[str, str]
    senior_token: Optional[str] = None
    status_code: Optional[int] = None
    redirect_location: Optional[str] = None
    error_message: Optional[str] = None
    response_headers: Optional[Dict[str, str]] = None

    def __post_init__(self):
        """Pós-processamento após inicialização"""
        # Se success é True mas senior_token está vazio, tentar extrair dos cookies
        if self.success and not self.senior_token and 'com.senior.token' in self.cookies:
            self.senior_token = self.cookies['com.senior.token']

    @property
    def has_senior_token(self) -> bool:
        """Verifica se possui o token principal da Senior"""
        return self.senior_token is not None and len(self.senior_token) > 0

    @property
    def session_cookies(self) -> Dict[str, str]:
        """Retorna apenas os cookies de sessão importantes"""
        important_cookies = [
            'com.senior.token',
            'JSESSIONID',
            'com.senior.idp.state',
            'TS018608fa'
        ]
        return {k: v for k, v in self.cookies.items() if k in important_cookies}

    def get_cookie(self, name: str) -> Optional[str]:
        """
        Obtém um cookie específico pelo nome

        Args:
            name (str): Nome do cookie

        Returns:
            str or None: Valor do cookie ou None se não encontrado
        """
        return self.cookies.get(name)

    def get_decoded_token(self) -> Optional[Dict]:
        """
        Retorna o token decodificado como dicionário

        Returns:
            Dict or None: Token decodificado ou None se não disponível
        """
        if not self.has_senior_token:
            return None

        try:
            from .token_decoder import SeniorTokenDecoder
            return SeniorTokenDecoder.decode_token(self.senior_token)
        except ImportError:
            # Fallback manual se não conseguir importar
            import urllib.parse
            import json
            try:
                decoded = urllib.parse.unquote(self.senior_token)
                return json.loads(decoded)
            except:
                return None

    def get_token_info(self) -> Dict:
        """
        Retorna informações estruturadas do token

        Returns:
            Dict: Informações do token organizadas
        """
        decoded = self.get_decoded_token()
        if not decoded:
            return {}

        try:
            from .token_decoder import SeniorTokenDecoder
            return SeniorTokenDecoder.get_token_info(decoded)
        except ImportError:
            # Fallback básico
            return {
                'username': decoded.get('username'),
                'email': decoded.get('email'),
                'access_token': decoded.get('access_token'),
                'expires_in': decoded.get('expires_in')
            }

    def to_dict(self) -> Dict:
        """Converte o resultado para dicionário"""
        result = {
            'success': self.success,
            'senior_token': self.senior_token,
            'has_senior_token': self.has_senior_token,
            'cookies': self.cookies,
            'session_cookies': self.session_cookies,
            'status_code': self.status_code,
            'redirect_location': self.redirect_location,
            'error_message': self.error_message,
            'response_headers': self.response_headers
        }

        # Adicionar token decodificado se disponível
        decoded_token = self.get_decoded_token()
        if decoded_token:
            result['decoded_token'] = decoded_token
            result['token_info'] = self.get_token_info()

        return result

    def __str__(self) -> str:
        """Representação string do resultado"""
        status = "SUCCESS" if self.success else "FAILED"
        token_status = "✓" if self.has_senior_token else "✗"
        return f"AuthenticationResult({status}, Token: {token_status}, Cookies: {len(self.cookies)})"
