document.addEventListener("DOMContentLoaded", function() {
    const stateSelect = document.getElementById("state");
    const districtSelect = document.getElementById("district");
    const subDivisionSelect = document.getElementById("subdivision");
    const pincodeSelect = document.getElementById("pincode");

    // Fetch JSON data
    fetch('./static/state.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            const hierarchicalData = data.reduce((acc, item) => {
                const STATE = item.state.toUpperCase();
                acc[STATE] = {};
                item.districts.forEach(district => {
                    const DISTRICT = district.district.toUpperCase();
                    acc[STATE][DISTRICT] = {};
                    district.subdivisions.forEach(subdivision => {
                        const SUBDIVISION = subdivision.subdivision.toUpperCase();
                        acc[STATE][DISTRICT][SUBDIVISION] = subdivision.pincode.toUpperCase();
                    });
                });
                return acc;
            }, {});

            // Populate state options in alphabetical order
            const states = Object.keys(hierarchicalData).sort();
            states.forEach(state => {
                const option = document.createElement("option");
                option.value = state;
                option.textContent = state;
                stateSelect.appendChild(option);
            });

            stateSelect.addEventListener("change", function() {
                const state = this.value;
                const districts = Object.keys(hierarchicalData[state] || {}).sort();
                populateSelect(districtSelect, districts, "");
                districtSelect.disabled = !state;
                subDivisionSelect.disabled = true;
                pincodeSelect.disabled = true;
            });

            districtSelect.addEventListener("change", function() {
                const state = stateSelect.value;
                const district = this.value;
                const subDivisions = Object.keys(hierarchicalData[state][district] || {}).sort();
                populateSelect(subDivisionSelect, subDivisions, "");
                subDivisionSelect.disabled = !district;
                pincodeSelect.disabled = true;
            });

            subDivisionSelect.addEventListener("change", function() {
                const state = stateSelect.value;
                const district = districtSelect.value;
                const subDivision = this.value;
                const pincode = hierarchicalData[state][district][subDivision] || "";
                populateSelect(pincodeSelect, [pincode], "");
                pincodeSelect.disabled = !subDivision;
            });

            function populateSelect(selectElement, data, placeholder) {
                selectElement.innerHTML = `<option value="">${placeholder}</option>`;
                data.forEach(item => {
                    const option = document.createElement("option");
                    option.value = item;
                    option.textContent = item;
                    selectElement.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Error loading the JSON data:', error);
        });
});
