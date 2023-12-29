
selectedElement = null;
function makeDraggable(evt) {
    svg = evt.target;
    setupZoom(svg);
    svg.addEventListener('mousedown', startDrag);
    svg.addEventListener('mousemove', drag);
    svg.addEventListener('mouseup', endDrag);
    svg.addEventListener('mouseleave', endDrag)
}
function makeDraggableById(id) {
    alert("Getting element by id? " + id)
    svg = document.getElementById(id);
    setupZoom(svg);
    svg.addEventListener('mousedown', startDrag);
    svg.addEventListener('mousemove', drag);
    svg.addEventListener('mouseup', endDrag);
    svg.addEventListener('mouseleave', endDrag)
}

function setupZoom(svg) {
    let currentScale = 1;
    console.log("Zoom setup complete")

    function zoom(evt) {
        console.log("Zooming")
        evt.preventDefault();
        const scaleFactor = 0.1;
        const zoomDirection = evt.deltaY > 0 ? -1 : 1;

        // Determine the new scale factor
        currentScale *= (1 + scaleFactor * zoomDirection);

        // Set the transform attribute with the new scaling
        svg.setAttribute('transform', 'scale(' + currentScale + ')');

    }

    svg.addEventListener('wheel', zoom);


}
function startDrag(evt) {
    //alert("starting drag " + evt.target.id);
    selectedElement = true;
    offset = getMousePosition(evt);

    var draggableElements = svg.querySelectorAll('.draggable');
    draggableElements.forEach(function (el) {
        var transforms = el.transform.baseVal;
        if (transforms.length === 0 || transforms.getItem(0).type !== SVGTransform.SVG_TRANSFORM_TRANSLATE) {
            // Create a transform that translates by (0, 0)
            var translate = svg.createSVGTransform();
            translate.setTranslate(0, 0);
            el.transform.baseVal.insertItemBefore(translate, 0);
        }
        // Ensure initial drag point is set
        if (!el._dragPoint) {
            el._dragPoint = svg.createSVGPoint();
        }
    });
}


function resetDrag() {
    var draggableElements = svg.querySelectorAll('.draggable');
    console.log("Resetting " + draggableElements.length + " draggable elements");

    draggableElements.forEach(function (el) {
        // Remove any translate transform
        var transforms = el.transform.baseVal;
        if (transforms.length > 0 && transforms.getItem(0).type === SVGTransform.SVG_TRANSFORM_TRANSLATE) {
            transforms.removeItem(0);
            //console.log("Removing transform");
        }

        // Remove the cached _dragPoint property
        if (el._dragPoint) {
            //console.log("Removing drag point");
            delete el._dragPoint;
        }
    });

    // Reset any global variables related to dragging here, if needed
    selectedElement = null; // or false, depending on its intended use
    offset = null; // or reset to some initial value

}

function drag(evt) {
    if (selectedElement) {
        //alert("continueing " + selectedElement.id)

        //evt.preventDefault();
        var coord = getMousePosition(evt);

        var dx = coord.x - offset.x;
        var dy = coord.y - offset.y;

        // Move each draggable element
        var draggableElements = svg.querySelectorAll('.draggable');
        draggableElements.forEach(function (el) {
            var transform = el.transform.baseVal.getItem(0);
            var pt = el._dragPoint;
            pt.x += dx;
            pt.y += dy;
            transform.setTranslate(pt.x, pt.y);
        });

        offset = coord;
    }

}
function endDrag(evt) {
    selectedElement = null;
}

function getMousePosition(evt) {
    var CTM = svg.getScreenCTM();
    return {
        x: (evt.clientX - CTM.e) / CTM.a,
        y: (evt.clientY - CTM.f) / CTM.d
    };
}