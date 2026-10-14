# Visual asset sources

## Freight Tiger branding

Official reference: https://freighttiger.com/

- Logo: https://freighttiger.com/ft/logo.svg (unaltered local copy)
- Alliance regular, medium, and semibold webfonts: publicly served by the official site's `/_next/static/media/` assets; exact original filenames recorded below.
- UI tokens sampled from the official CSS: amber `#ffbe07`, ink `#0b0a0a`, stone `#433e37`, warm muted `#8c8273`, surface `#f7f7f5`, border `#e8e6e3`.

Font source filenames:

- `alliance_regular-s.p.406ttw0c-ddm0.woff2`
- `alliance_medium-s.p.3pofoizoycqjk.woff2`
- `alliance_semibold-s.p.3e3a92_r25g15.woff2`

These assets retain their original ownership. This dashboard is an independent internship case-study prototype, identified as such in its interface; it is not an official Freight Tiger product.

## India boundary

Source: https://github.com/datameet/maps/blob/master/Country/india-soi.geojson

Dataset property: `Survey of India State Map, Datameet`.
Attribution: DataMeet community India boundaries, CC BY 4.0.

The outer rings are simplified with Douglas–Peucker tolerance of 0.025 degrees and rounded to five decimal places. All 618 polygon components, including islands, are retained. This is a geographic display, not a cadastral or navigation map. Boundaries follow this source dataset; no custom replacement outline is drawn. The northeast and offshore islands remain at their geographic coordinates.

Projection uses a longitude scale corrected by cos(22 degrees), followed by an orthographic 3D camera. Default yaw is zero for a recognizable north-up view; users may orbit the camera. Truck positions, speeds, and routes remain illustrative rather than GPS or road-navigation data.
