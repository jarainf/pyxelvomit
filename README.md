# Pyxelvomit

The worst way to hog your CPU-performance. I consider this project to be END OF LIFE. If you want to do changes, feel free to do pull requests, however I won't be revisiting this any time soon. See [pixelvomit](https://github.com/jarainf/pixelvomit).

## Usage:
Change the variables in the code to your liking. They currently aren't documented and probably never will be. I've moved on to greener pastures with my C-Pixelflut-Server [pixelvomit](https://github.com/jarainf/pixelvomit).  
After that, start the server:  
`python pyxelvomit.py`

## Known Bugs (won't fix):
- This server is quite slow. This can be attributed to python-sockets being quite slow, but the code could also benefit from optimisations
- framebuffers will behave differently on many devices. Some have "padding" on the side, some have padding at the "bottom". This does not always correspond to an array shape that is proportional to your resolution. This will break pyxelvomit.
