import folium
import branca.colormap as cm

#32.65, 35.27

def build_forecast_map(rows, horizon: str):
    fol_map = folium.Map(location=[32.65, 35.27], zoom_start=10)
    
    step = 0.025  # half of 0.05
    max_precip = max(r[horizon] for r in rows) or 1
    colormap = cm.LinearColormap(['blue', 'cyan', 'yellow', 'red'], vmin=0, vmax=max_precip)

    for row in rows:
        lat, lon = row['lat'], row['lon']
        precip = row[horizon]
        color = colormap(precip)
        
        folium.Rectangle(
            bounds=[[lat - step, lon - step], [lat + step, lon + step]],
            color=None,
            fill=True,
            fill_color=color,
            fill_opacity=0.4,
            tooltip=f"Cell {row['cell_id']}: {precip:.2f}mm"
        ).add_to(fol_map)

    return fol_map
