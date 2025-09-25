from django import forms
import json
from django.utils.safestring import mark_safe   # <- add this
from django.utils.html import format_html


class KeyValueJSONWidget(forms.Widget):
    """
    Renders a table where the user can add/remove key/value rows.
    Stores result in a hidden input as JSON.
    """
    def render(self, name, value, attrs=None, renderer=None):
        value = value or {}
        if isinstance(value, str):
            try:
                value = json.loads(value or "{}")
            except Exception:
                value = {}
        # build a simple HTML scaffold
        attrs = self.build_attrs(self.attrs, attrs or {})
        attrs_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        html = f"""
<div class="kvjson-widget" data-kvjson {attrs_str}>
  <input type="hidden" name="{name}" value='{json.dumps(value)}' />
  <table class="kvjson-table">
    <thead><tr><th style="width:40%">Key</th><th>Value</th><th style="width:1%"></th></tr></thead>
    <tbody class="kvjson-rows"></tbody>
  </table>
  <button type="button" class="kvjson-add">+ Add</button>
  <small class="kvjson-hint">Keys must be unique. Values can be text, numbers, true/false, or JSON (e.g., ["HDMI","DP"]).</small>
</div>
"""
        return mark_safe(html)

    class Media:
        css = {"all": ("assets/kvjson/kvjson.css",)}
        js = ("assets/kvjson/kvjson.js",)
