def extract_competition_id(url: str) -> str:
    """
    Extrae el ID de la competición desde una URL de Transfermarkt.

    """
    if "/wettbewerb/" in url:
        return url.split("/wettbewerb/")[1].split("/")[0].split("?")[0]
    return None