from django import template
from assets.access import (
    can_view_asset, can_edit_asset, can_delete_asset, can_assign_asset,
    can_view_category, can_edit_category, can_delete_category,
    can_view_assignment, can_edit_assignment, can_delete_assignment
)

register = template.Library()

register.simple_tag(can_view_asset)
register.simple_tag(can_edit_asset)
register.simple_tag(can_delete_asset)
register.simple_tag(can_assign_asset)

register.simple_tag(can_view_category)
register.simple_tag(can_edit_category)
register.simple_tag(can_delete_category)

register.simple_tag(can_view_assignment)
register.simple_tag(can_edit_assignment)
register.simple_tag(can_delete_assignment)
