import sys
import pickle
from typing import Union
from interop_types import ParametricObjectNode, BlendQueryBuildException

def main():
  try:
    from setup_venv import setup_venv
    setup_venv()

    # TODO: Investigate return code issue.
    import cadquery
    import build123d

    ParametricShape = Union[cadquery.Shape, build123d.Shape]
    ParametricObject = Union[
        ParametricShape,
        cadquery.Workplane,
        cadquery.Assembly,
        build123d.Builder,
    ]

    def parse_parametric_script(script: str):
        locals = {}
        globals = {
            "cadquery": cadquery,
            "cq": cadquery,
            # Exclude Build123d here as most examples already import it and it is usually a spread import
        }
        exec(script, globals, locals)

        # Filter out all non-constructive and hidden objects (those prefixed with "_")
        parametric_objects = [
            value
            for name, value in locals.items()
            if isinstance(value, ParametricObject) and not name.startswith("_")
        ]

        return [
            parse_parametric_object(object, "ROOT", None)
            for object in parametric_objects
        ]

    def parse_parametric_object(object: ParametricObject, name: str, material: Union[str, None]) -> ParametricObjectNode:
        # Use object properties otherwise inherit them from parent
        name = object.name if (hasattr(object, 'name') and object.name) else name
        material = object.material if (hasattr(object, 'material') and object.material) else material

        # TODO: Do we really need to support per-child assemblies? Could we just get CadQuery to flatten into a shape for us..
        if isinstance(object, cadquery.Assembly):
            return ParametricObjectNode(
                name=name, 
                material=material,
                children=[parse_parametric_object(child, name, material) for child in object.shapes + object.children],
            )

        if isinstance(object, ParametricShape):
            shape = object
        elif isinstance(object, cadquery.Workplane):
            # TODO: `object.val().wrapped` is not guaranteed to be `Shape`
            shape = cadquery.Shape(object.val().wrapped)
        elif isinstance(object, build123d.Builder):
            shape = object._obj
        else:
            raise BlendQueryBuildException(
                "Failed to parse parametric object; Unsupported object type (" + str(type(object)) + ")."
            )
        
        # Tolerances are a trade off between accuracy and performance
        # `0.01` is decided from a standard of `1u=1m`
        # TODO: Expose this via object so that it may be configured by the user for generating more/less complex geometry
        tolerance = 0.01
        angular_tolerance = 0.01
        vertices, faces = shape.tessellate(tolerance, angular_tolerance)
        vertices = [
            vertex.toTuple() if hasattr(vertex, "toTuple") else vertex.to_tuple()
            for vertex in vertices
        ]
        
        return ParametricObjectNode(
            name=name,
            material=material,
            vertices=vertices,
            faces=faces,
        )

    parametric_script = pickle.loads(sys.stdin.buffer.read())
    parametric_objects = parse_parametric_script(parametric_script)
    sys.stdout.buffer.write(pickle.dumps(parametric_objects))
    sys.stdout.buffer.flush()
    sys.exit(0)
  except Exception as exception:
    sys.stdout.buffer.write(pickle.dumps(exception))
    sys.stdout.buffer.flush()
    sys.exit(1)

if __name__ == "__main__":
    main()
