import L from 'leaflet';

const iconRed = new L.Icon({
    iconUrl: require("./img/marker-red.svg").default,
    iconSize: [36, 36],
    iconAnchor: [18, 36],
});

const iconBlue = new L.Icon({
    iconUrl: require("./img/marker-blue.svg").default,
    iconSize: [36, 36],
    iconAnchor: [18, 36],
});

const iconBlueSmall = new L.Icon({
    iconUrl: require("./img/marker-blue-light.svg").default,
    iconSize: [25, 25],
    iconAnchor: [12.5, 25],
});


// https://www.svgrepo.com/collection/transportation-glyph-icons/

const iconAirplane = new L.Icon({
    iconUrl: require("./img/airplane.svg").default,
    iconSize: [50, 50],
});
const iconTrain = new L.Icon({
    iconUrl: require("./img/train.svg").default,
    iconSize: [50, 50],
});
const iconBus = new L.Icon({
    iconUrl: require("./img/bus.svg").default,
    iconSize: [50, 50],
});
const iconCar = new L.Icon({
    iconUrl: require("./img/car.svg").default,
    iconSize: [50, 50],
});



export { iconRed, iconBlue, iconBlueSmall };
export { iconAirplane, iconTrain, iconBus, iconCar };