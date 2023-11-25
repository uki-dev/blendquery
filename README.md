# BlendQuery
[CadQuery](https://github.com/CadQuery/cadquery) and [Build123d](https://github.com/gumyr/build123d) integration for Blender

![image](https://user-images.githubusercontent.com/7185241/208252834-c1cdd4eb-b37c-4fd0-bf71-3cdb8ad4bca0.png)

## Installation
[Installing Add-ons](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html#installing-add-ons)

## Usage
The BlendQuery panel can be located under `Object Properties`, where you are able to select your script to generate into the Blender scene.

![image](https://github.com/uki-dev/blendquery/assets/7185241/3012c51f-08a3-4b3f-a9ea-beb6ddbfc08b)

### Showing / Hiding Objects
BlendQuery will automatically genenerate any topology object variables from the global scope of your script into the Blender scene. To prevent this, simply prefix your variable with `_`.

