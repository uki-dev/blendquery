# TODO: Fix typing
import bpy
import cadquery
from cadquery import Workplane, Compound, Shape, Assembly


def generate(
    object,
    tolerance=0.1,
    angularTolerance=0.1,
):
    if isinstance(object, Assembly):
        compound = object.toCompound()
    elif isinstance(object, Workplane):
        compound = cadquery.exporters.utils.toCompound(object)
    elif isinstance(object, Compound):
        compound = object
    else:
        raise ValueError("Unsupported type: " + str(type(object)))

    return [generate_from_compound(compound, tolerance, angularTolerance)]


def generate_from_compound(
    compound: Compound,
    tolerance=0.1,
    angularTolerance=0.1,
):
    tessellation = compound.tessellate(tolerance, angularTolerance)

    vertices = []
    for vertex in tessellation[0]:
        vertices.append(vertex.toTuple())
    faces = tessellation[1]

    mesh = bpy.data.meshes.new("mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    object = bpy.data.objects.new("object", mesh)
    bpy.context.scene.collection.objects.link(object)
    return object
