from django import template

register = template.Library()


@register.filter(name='cents_to_euros')
def cents_to_euros(value):
    """
    Convertit un montant en centimes en affichage euros formaté.
    Exemple: 125000 -> "1 250,00 €"
    """
    if value is None:
        return ""
    
    try:
        euros = int(value) / 100
        # Formatage avec espace comme séparateur de milliers et virgule pour les décimales
        formatted = f"{euros:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")
        return f"{formatted} €"
    except (ValueError, TypeError):
        return ""


@register.filter(name='format_slug')
def format_slug(value):
    """Transforme un titre en slug"""
    from django.utils.text import slugify
    return slugify(value)
