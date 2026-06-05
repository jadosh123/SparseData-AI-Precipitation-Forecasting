import folium
import bisect
from branca.element import MacroElement
from jinja2 import Template

#32.65, 35.27

def build_forecast_map(rows, horizon: str):
    fol_map = folium.Map(location=[32.65, 35.27], zoom_start=10)
    
    step = 0.005  # half of 0.05

    PRECIP_LEVELS = [0.1, 0.2, 0.7, 1.2, 2.0, 4.0, 6.0, 9.0, 13.0, 18.0, 24.0, 30.0, 40.0, 50.0, 100.0, 200.0]
    PRECIP_COLORS = [
        '#0000FF',  # blue          0.1
        '#00CCFF',  # cyan          0.2
        '#00FFEE',  # tinted cyan   0.7
        '#006600',  # dark grass    1.2
        '#007A00',  # darker green  2.0
        '#009900',  # tinted green  4.0
        '#00BB00',  # green         6.0
        '#88CC00',  # light grass   9.0
        '#FFFF00',  # yellow        13
        '#FFEE00',  # tinted yellow 18
        '#FFAA00',  # orange/yellow 24
        '#FF6600',  # orange        30
        '#FF3300',  # red/orange    40
        '#CC0000',  # red           50
        '#990033',  # deeper pink   100
        '#FF69B4',  # pink          200
    ]

    rows_html = "".join(
        f'<tr><td style="background:{c};width:20px;">&nbsp;</td><td style="padding:0 4px;font-size:11px;">{l}</td></tr>'
        for c, l in reversed(list(zip(PRECIP_COLORS, PRECIP_LEVELS)))
    )
    legend = MacroElement()
    legend._template = Template(f"""
        {{% macro html(this, kwargs) %}}
        <style>
            @media (max-width: 639px) {{
                #precip-legend {{ bottom: 5px !important; }}
                #precip-legend td {{ font-size: 8px !important; padding: 0 2px !important; }}
                #precip-legend td:first-child {{ width: 12px !important; }}
                #precip-legend b {{ font-size: 8px !important; }}
            }}
        </style>
        <div id="precip-legend" style="position:fixed;bottom:30px;right:10px;z-index:1000;background:white;
                    padding:6px;border:1px solid #ccc;font-family:sans-serif;">
            <b style="font-size:11px;">mm/h</b>
            <table style="border-collapse:collapse;margin-top:2px;">{rows_html}</table>
        </div>
        {{% endmacro %}}
    """)
    legend.add_to(fol_map)

    for row in rows:
        lat, lon = row['lat'], row['lon']
        precip = row[horizon]
        band = bisect.bisect_right(PRECIP_LEVELS, precip) - 1
        color = PRECIP_COLORS[min(band, len(PRECIP_COLORS) - 1)] if precip >= 0.1 else "#FFFFFF"
        
        folium.Rectangle(
            bounds=[[lat - step, lon - step], [lat + step, lon + step]],
            color=None,
            fill=True,
            fill_color=color,
            fill_opacity=0.4,
            tooltip=f"Cell {row['cell_id']}: {precip:.2f}mm"
        ).add_to(fol_map)

    return fol_map
