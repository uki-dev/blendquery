import cadquery

u = 2
h = 2
lh = 4.1 / 2
th = 1.17 / 2

# body
keycap = cadquery.Workplane('XZ').box(16 * u, 16, h).edges('|Y').fillet(2)
# stem mount
keycap = keycap.faces('<Y').polyline([
    (-lh, 0),
    (-lh, th),
    (-th, th),
    (-th, lh),
    (th, lh),
    (th, th),
    (lh, th),
    (lh, 0),
]).mirrorX().extrude(h / 2, 'cut')

assembly = cadquery.Assembly(metadata = {
    'material': 'acrylic',
})
assembly.add(keycap)

result = assembly