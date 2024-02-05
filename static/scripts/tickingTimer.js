// Function to call when divs with 'tickingTimer' class are added to the DOM
function onTimerDivAdded(addedNodes) {
    //console.log("Got this far")
    addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE && node.classList.contains('tickingTimer')) {
            console.log("New tickingTimer added: ", node);
            // You can invoke any function here to initialize the added div
            initializeTimer(node);
        }
    });
}

var elements_to_update = []

// Suppose this function initializes your timer
function initializeTimer(element) {
    // Your logic to initialize the timer, e.g., attaching events or setting up data
    //console.log("Initializing timer for element", element);
    elements_to_update.push(element)

}

function updateTimers() {
    expired_elements = []
    elements_to_update.forEach(element => {
        // Your logic to update the timer

        // if the element has been deleted 
        if (element.parentElement == null) {
            expired_elements.push(element)
        }

        var timerText = element.textContent;
        var matches = timerText.match(/(\d+)s\s\((\d+)h\s(\d+)m\s(\d+)s\)/);

        if (matches) {
            let [, totalSeconds, hours, minutes, seconds] = matches.map(Number);
            //console.log("matched total seconds [", totalSeconds, " ]");

            if (totalSeconds > 0) {
                totalSeconds -= 1; // Decrease by one second
                totalSeconds = Math.max(totalSeconds, 0); // Ensure timer doesn't go negative

                hours = Math.floor(totalSeconds / 3600);
                totalSeconds %= 3600;
                minutes = Math.floor(totalSeconds / 60);
                seconds = totalSeconds % 60;

                // Update the div with the new timer value
                element.textContent = `${totalSeconds}s (${hours}h ${minutes}m ${seconds}s)`;
            } else {
                // Optionally clear the interval or handle the expiration of the timer here
                element.textContent = `0s (0h 0m 0s)`;
                // use regex to extract the seconds
                // then use JS to split it back out into SSs (HHh MMm SSs)

                //console.log("Timer updated for element", element, element.innerHTML);
            };
        }
    });

    // remove expired elements
    expired_elements.forEach(element => {
        elements_to_update.splice(elements_to_update.indexOf(element), 1);
    });
}

// Options for the observer (which mutations to observe)
const config = { childList: true, subtree: true };

// Callback function to execute when mutations are observed
const callback = function (mutationsList) {
    console.log("Callback called")
    for (const mutation of mutationsList) {
        if (mutation.type === 'childList') {
            // Check added nodes
            //console.log("Mutation observed: ", mutation.addedNodes)
            onTimerDivAdded(mutation.addedNodes);
        }
    }
};


// Create an instance of MutationObserver with the callback
const observer = new MutationObserver(callback);

// Start observing the document body for configured mutations
window.addEventListener('load', () => {
    observer.observe(document.body, config);

});

// every 1 second call the updateTimers function
window.setInterval(updateTimers, 1000);

window.addEventListener('load', () => {
    // Initialize timers that are already present in the DOM at load time
    const existingTimers = document.querySelectorAll('.tickingTimer');
    onTimerDivAdded(existingTimers);

    // Now start the MutationObserver to listen for added nodes with 'tickingTimer' class in the future
    observer.observe(document.body, config);
});


console.log("Ticking timer script loaded");