function initilaizeBehaviourIdAndSubmitButton() {
    var selectElement = document.getElementById('behaviour_id');
    selectElement.addEventListener('change', function () {

        console.log("Yeet")
        // Get the selected option and its data-params attribute
        var selectedOption = this.options[this.selectedIndex];
        var params = selectedOption.getAttribute('params');

        console.log(params)
        // Parse the JSON string
        var jsonParams = JSON.parse(params);
        // Clear previous elements
        var container = document.getElementById('behaviour_param_controls');
        container.innerHTML = '';

        // Dynamically create HTML elements based on jsonParams
        Object.keys(jsonParams).forEach(function (key) {
            var value = jsonParams[key];
            console.log("key", "value")
            var colDiv = document.createElement('div');
            colDiv.className = 'col-md-6';

            // Create the form-floating div
            var formFloatingDiv = document.createElement('div');
            formFloatingDiv.className = 'form-floating';

            // Create the input field
            var input = document.createElement('input');
            input.id = key;
            input.name = key;  //If name isn't sent, the FormData javascript omits this.
            input.className = 'form-control bg-dark text-success';
            input.value = value;
            input.setAttribute('aria-label', value);

            // Create the label
            var label = document.createElement('label');
            label.htmlFor = key;
            label.className = 'text-success';
            label.textContent = key; // or any other text you want to display in the label

            // Append the input and label to the formFloatingDiv
            formFloatingDiv.appendChild(input);
            formFloatingDiv.appendChild(label);

            // Append the formFloatingDiv to the colDiv
            colDiv.appendChild(formFloatingDiv);

            // Add the new colDiv to our container
            container.appendChild(colDiv);

        });
    });


    var form = document.getElementById('behaviour_form');

    form.addEventListener('submit', function (event) {
        event.preventDefault(); // Prevent the form from submitting via the browser

        var formData = new FormData(form);
        console.log("form data", formData)
        console.log("ready to submit task!")
        var object = {};
        formData.forEach(function (value, key) {
            object[key] = value;
        });

        var json = JSON.stringify(object);

        fetch('/behaviour/submit/' + object["ship_symbol"] + "/" + object["behaviour_id"], { // Replace with your endpoint
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: json
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Network response was not ok ' + response.statusText);
                }
                return response.json();
            })
            .then(function (data) {
                // Handle response data
                console.log(data); // Display response in the console
                resultContainer.textContent = JSON.stringify(data, null, 2); // Display nicely formatted JSON
            })
            .catch(function (error) {
                console.error('There has been a problem with your fetch operation:', error);
                resultContainer.textContent = 'Error: ' + error.message;
            });
    });

}


console.log("Yeet")
document.addEventListener('DOMContentLoaded', function () {
    initilaizeBehaviourIdAndSubmitButton();
});



function onTimerDivAdded(addedNodes) {
    //console.log("Got this far")
    addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE && node.id == 'behaviour_id') {
            console.log("New tickingTimer added: ", node);
            // You can invoke any function here to initialize the added div
            initilaizeBehaviourIdAndSubmitButton();
        }
    });
}
