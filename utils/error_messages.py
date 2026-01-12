"""User-friendly error messages for elderly users"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Error message translations (Serbian - user-friendly)
ERROR_MESSAGES = {
    # HTTP Errors
    'HTTPError:400': "Neispravan zahtev. Proverite unete podatke.",
    'HTTPError:401': "Pristup odbijen. Proverite korisničko ime i lozinku.",
    'HTTPError:403': "Pristup zabranjen. Možda nemate dozvolu za ovaj sadržaj.",
    'HTTPError:404': "Sadržaj nije pronađen. Možda je uklonjen ili premešten.",
    'HTTPError:500': "Problem na serveru. Pokušajte ponovo kasnije.",
    'HTTPError:502': "Server ne odgovara. Pokušajte ponovo za nekoliko minuta.",
    'HTTPError:503': "Server je trenutno nedostupan. Pokušajte kasnije.",
    'HTTPError:504': "Server ne odgovara - prekoračeno vreme čekanja.",

    # Connection Errors
    'ConnectionError': "Ne mogu da se povežem na internet. Proverite internet konekciju.",
    'Timeout': "Server ne odgovara. Pokušajte ponovo za nekoliko trenutaka.",
    'TimeoutError': "Vreme čekanja je isteklo. Proverite internet brzinu.",
    'ConnectTimeout': "Ne mogu da se povežem - server ne odgovara.",
    'ReadTimeout': "Server sporo odgovara. Pokušajte ponovo.",

    # Network Errors
    'NetworkError': "Problem sa mrežom. Proverite internet konekciju.",
    'DNSError': "Ne mogu da pronađem server. Proverite internet konekciju.",
    'SSLError': "Sigurnosna greška. Proverite vreme i datum na računaru.",

    # File Errors
    'FileNotFoundError': "Fajl nije pronađen. Proverite putanju.",
    'PermissionError': "Nemate dozvolu za pristup ovom fajlu.",
    'IOError': "Greška pri čitanju/pisanju fajla.",

    # Playlist Errors
    'InvalidPlaylist': "Playlista nije ispravna. Proverite format i sadržaj.",
    'EmptyPlaylist': "Playlista je prazna. Nema dostupnih kanala ili filmova.",
    'InvalidURL': "Adresa (URL) nije ispravna. Proverite unos.",
    'InvalidM3U': "M3U fajl nije ispravan. Proverite format fajla.",

    # Xtream Errors
    'XtreamAuthError': "Greška pri prijavi na Xtream server. Proverite korisničko ime i lozinku.",
    'XtreamServerError': "Xtream server nije dostupan. Pokušajte kasnije.",

    # Video Player Errors
    'StreamNotAvailable': "Video nije dostupan. Možda je uklonjen ili nedostupan.",
    'StreamTimeout': "Video se ne učitava. Proverite internet brzinu.",
    'CodecError': "Video format nije podržan.",
    'PlaybackError': "Greška pri reprodukciji videa. Pokušajte ponovo.",

    # TMDB Errors
    'TMDBError': "Ne mogu da učitam informacije o filmu. TMDB server nedostupan.",
    'TMDBTimeout': "TMDB server ne odgovara. Ocena filma nedostupna.",
    'TMDBNotFound': "Film nije pronađen u bazi filmova.",

    # General Errors
    'UnknownError': "Došlo je do nepoznate greške. Pokušajte ponovo.",
    'ValueError': "Neispravna vrednost. Proverite unete podatke.",
    'KeyError': "Podatak nije pronađen.",
}


def get_user_friendly_error(exception: Exception, context: str = "") -> str:
    """
    Convert Python exception to user-friendly Serbian message

    Args:
        exception: The exception object
        context: Additional context (e.g., "playlist_loading", "video_playback")

    Returns:
        User-friendly error message in Serbian
    """
    exception_type = type(exception).__name__
    exception_str = str(exception)

    # Try to match specific error patterns
    error_key = None

    # HTTP errors (requests library)
    if "HTTPError" in exception_type:
        # Extract HTTP code if available
        if hasattr(exception, 'response') and exception.response:
            status_code = exception.response.status_code
            error_key = f"HTTPError:{status_code}"
        else:
            error_key = "HTTPError:500"

    # Connection errors
    elif "ConnectionError" in exception_type:
        error_key = "ConnectionError"
    elif "Timeout" in exception_type:
        error_key = "Timeout"
    elif "TimeoutError" in exception_type:
        error_key = "TimeoutError"
    elif "ConnectTimeout" in exception_type:
        error_key = "ConnectTimeout"
    elif "ReadTimeout" in exception_type:
        error_key = "ReadTimeout"

    # File errors
    elif "FileNotFoundError" in exception_type:
        error_key = "FileNotFoundError"
    elif "PermissionError" in exception_type:
        error_key = "PermissionError"
    elif "IOError" in exception_type:
        error_key = "IOError"

    # Value errors
    elif "ValueError" in exception_type:
        error_key = "ValueError"
    elif "KeyError" in exception_type:
        error_key = "KeyError"

    # Context-specific errors
    if context == "tmdb":
        if error_key == "Timeout":
            error_key = "TMDBTimeout"
        elif error_key:
            error_key = "TMDBError"

    # Get message from dictionary
    if error_key and error_key in ERROR_MESSAGES:
        message = ERROR_MESSAGES[error_key]
    elif exception_type in ERROR_MESSAGES:
        message = ERROR_MESSAGES[exception_type]
    else:
        # Fallback to unknown error
        message = ERROR_MESSAGES['UnknownError']

    # Log technical details for debugging
    logger.debug(f"Error converted: {exception_type} -> {message} (original: {exception_str})")

    return message


def format_error_with_action(error_message: str, suggested_action: Optional[str] = None) -> str:
    """
    Format error message with suggested action

    Args:
        error_message: The error message
        suggested_action: Suggested action (optional)

    Returns:
        Formatted message with action
    """
    if suggested_action:
        return f"{error_message}\n\nPredlog: {suggested_action}"
    return error_message


# Common suggested actions
SUGGESTED_ACTIONS = {
    'network': "Proverite da li je internet aktivan i pokušajte ponovo.",
    'credentials': "Proverite da li ste uneli tačno korisničko ime i lozinku.",
    'retry': "Pokušajte ponovo za nekoliko trenutaka.",
    'contact_support': "Ako problem i dalje postoji, kontaktirajte podršku.",
    'check_url': "Proverite da li ste uneli tačnu adresu (URL).",
    'restart': "Pokušajte da zatvorite i ponovo pokrenete aplikaciju.",
}
