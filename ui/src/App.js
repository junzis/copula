import 'bootstrap/dist/css/bootstrap.min.css';
import "leaflet/dist/leaflet.css"
import './App.css';

import {
  MapContainer, TileLayer, ZoomControl, Marker, Circle,
  CircleMarker, Tooltip, Polyline, Popup, useMap
} from 'react-leaflet'

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import L from 'leaflet';


import { iconRed, iconBlue, iconBlueSmall, iconAirplane, iconTrain, iconBus, iconCar } from "./Icons"
import ControlPanel from './ControlPanel';

const cartoDBTile = {
  url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  subdomains: 'abcd',
  maxZoom: 20
};

const colors = {
  flight: 'red',
  train: 'green',
  bus: 'blue',
  car: 'purple'
};



function App() {
  const [origin, setOrigin] = useState('Amsterdam');
  const [destMarkers, setDestMarkers] = useState([]);
  const [origMarkers, setOrigMarkers] = useState([]);
  const [selectedDest, setSelectedDest] = useState(null);
  const [popup, setPopup] = useState(null);
  const [summary, setSummary] = useState([]);

  useEffect(() => {
    axios.get(`http://localhost:8000/destinations/${origin}`)
      .then(response => {
        setOrigMarkers(response.data.origin);
        setDestMarkers(response.data.destination);
      })
      .catch(error => {
        console.error(error);
      });
  }, [origin]);

  const [routes, setRoutes] = useState({});

  const handleMarkerClick = (dest) => {
    if (dest[0] === selectedDest) {
      // Deselect destination and clear routes
      setSelectedDest(null);
      setRoutes({});
      setSummary([])
      return;
    }

    setSelectedDest(dest[0]);

    // Clear previous routes
    setRoutes({});

    // Get routes for each transport mode
    axios.get(`http://localhost:8000/route/${origin}/${dest[0]}`)
      .then(response => {
        setRoutes(response.data.routes);
        setSummary(response.data.summary);
      })
      .catch(error => console.error(error));
  };

  const handlePolylineClick = (event, transportMode, popupInfo) => {
    setPopup({
      position: event.latlng,
      transportMode: transportMode,
      popupInfo: popupInfo
    });
  };

  const MapUpdater = ({ routes }) => {
    const map = useMap();

    useEffect(() => {
      if (routes && Object.keys(routes).length > 0) {
        const allCoords = Object.values(routes).flatMap(data => data.route);
        let bounds = L.latLngBounds(allCoords);
        const padding = 0.2;
        const padding_west = 0.3;
        bounds = bounds.pad(padding);
        bounds.extend([bounds.getSouth(), bounds.getWest() - padding_west]);
        map.fitBounds(bounds);
      } else {
        map.flyTo([50, 8], 5);
      }
    }, [map, routes]);

    return null;
  }

  const Route = ({ transportMode, route, handlePolylineClick, popupInfo }) => {
    if (route.length === 0) return null;

    // Calculate the center of the route
    let center;
    if (route.length === 2) {
      center = [
        (route[0][0] + route[1][0]) / 2,
        (route[0][1] + route[1][1]) / 2
      ];
    } else {
      const centerIndex = Math.floor(route.length / 2);
      center = route[centerIndex];
    }

    return (
      <div key={transportMode}>
        <Polyline
          positions={route}
          color={colors[transportMode]}
          weight={20} // larger weight
          opacity={0} // transparent
          eventHandlers={{
            click: (event) => {
              handlePolylineClick(event, transportMode, popupInfo);
            },
          }}
        />
        <Polyline
          positions={route}
          weight={2}
          color={colors[transportMode]}
        />

        {/* Add circle markers */}
        {
          route.map((coord, i) => {
            if (transportMode === 'train' || transportMode === 'bus') {
              return (
                <CircleMarker
                  key={i}
                  center={coord}
                  radius={3}
                  color={colors[transportMode]}
                />
              );
            } else if (i === 0 || i === route.length - 1) {
              return <CircleMarker
                key={i}
                center={coord}
                radius={3}
                color={colors[transportMode]}
              />
            }
          })
        }

        <Marker position={center} icon={transportMode === 'flight' ? iconAirplane : (transportMode === 'train' ? iconTrain : (transportMode === 'bus' ? iconBus : iconCar))} />
      </div>
    );
  };


  return (
    <div className="App">
      <ControlPanel setOrigin={setOrigin} origin={origin}
        setSummary={setSummary} summary={summary}
        setSelectedDest={setSelectedDest} setRoutes={setRoutes} />

      <MapContainer
        center={[50, 8]}
        zoom={5}
        zoomDelta={1}
        zoomSnap={0.25}
        scrollWheelZoom={{ wheelPxPerZoomLevel: 60 }}
        zoomControl={false}
      >
        <MapUpdater routes={routes} />

        {popup && (
          <Popup position={popup.position}>
            <div>
              {popup.transportMode}
              <hr />
              {popup.popupInfo}
            </div>
          </Popup>
        )}

        <TileLayer {...cartoDBTile} />

        <ZoomControl position="topright" />

        {origMarkers.map(orig => (
          <Marker key={orig[0]} position={[orig[1], orig[2]]} icon={iconRed}>
            <Tooltip direction="top" offset={[0, -38]}>{orig[0]}</Tooltip>
          </Marker>
        ))}

        {origMarkers.map(orig => (
          <Circle
            key={orig[0]}
            center={[orig[1], orig[2]]}
            radius={5000}
          />
        ))}

        {destMarkers.map(dest => (
          <Marker
            key={dest[0]}
            position={[dest[1], dest[2]]}
            icon={selectedDest === dest[0] ? iconBlue : (selectedDest ? iconBlueSmall : iconBlue)}
            eventHandlers={{ click: () => handleMarkerClick(dest) }}
          >
            <Tooltip direction="top" offset={[0, -38]}>{dest[0]}</Tooltip>
          </Marker>
        ))}

        {destMarkers.map(dest => {
          if (dest[0] === selectedDest) {
            return (
              <Circle
                key={dest[0]}
                center={[dest[1], dest[2]]}
                radius={5000}
              />
            );
          }
          return null;  // for non-selected destinations
        })}

        {
          Object.entries(routes).map(([transportMode, data]) => {
            if (data.route.length === 0) return null;
            return (
              <Route
                key={transportMode}
                transportMode={transportMode}
                route={data.route}
                handlePolylineClick={handlePolylineClick}
                popupInfo={data.info}
              />
            );
          })
        }

      </MapContainer>
    </div>
  );
}

export default App;
