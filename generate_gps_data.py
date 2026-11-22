"""Generate a reproducible synthetic GPS dataset for GeoPulse."""

from pathlib import Path

import numpy as np
import pandas as pd


LATITUDE_BOUNDS = (18.40, 18.65)
LONGITUDE_BOUNDS = (73.75, 74.00)
SIMULATION_DATE = pd.Timestamp("2026-11-15")
RANDOM_SEED = 42
DEVICE_COUNT = 10_000
PINGS_PER_DEVICE = 10

RESIDENTIAL_AREAS = [
    (18.5074, 73.8077),  # Kothrud
    (18.5583, 73.8077),  # Aundh
    (18.5679, 73.9143),  # Viman Nagar
    (18.5089, 73.9260),  # Hadapsar
    (18.5308, 73.8475),  # Shivajinagar
    (18.5196, 73.8553),  # Camp
]

OFFICE_AREAS = [
    (18.5913, 73.7600),  # Hinjawadi
    (18.5590, 73.7860),  # Baner
    (18.5510, 73.9360),  # Kharadi
    (18.5160, 73.9270),  # Magarpatta
    (18.5308, 73.8475),  # Shivajinagar
]

TRANSIT_AREAS = [
    (18.5289, 73.8744),  # Pune railway station
    (18.5018, 73.8636),  # Swargate
    (18.5308, 73.8475),  # Shivajinagar
    (18.5679, 73.9143),  # Viman Nagar
    (18.5160, 73.9270),  # Hadapsar
]


def create_store_locations() -> pd.DataFrame:
    """Return fictional retail locations around Pune."""
    stores = [
        ("STORE001", "Koregaon Park Market", 18.5362, 73.8940),
        ("STORE002", "Camp Central Shops", 18.5196, 73.8553),
        ("STORE003", "FC Road Plaza", 18.5236, 73.8417),
        ("STORE004", "Deccan Square", 18.5165, 73.8410),
        ("STORE005", "Phoenix East Market", 18.5620, 73.9160),
        ("STORE006", "Amanora Retail Park", 18.5190, 73.9250),
        ("STORE007", "Westend Mall", 18.5640, 73.8120),
        ("STORE008", "Pavilion Market", 18.5360, 73.8280),
        ("STORE009", "Kothrud Arcade", 18.5060, 73.8070),
        ("STORE010", "Baner High Street", 18.5590, 73.7860),
        ("STORE011", "Seasons Market", 18.5150, 73.9270),
        ("STORE012", "Viman Nagar Square", 18.5670, 73.9140),
    ]
    return pd.DataFrame(
        stores, columns=["StoreID", "StoreName", "Latitude", "Longitude"]
    )


def create_commercial_zones() -> pd.DataFrame:
    """Return commercial and retail activity hubs with synthetic radii."""
    zones = [
        ("ZONE001", "Koregaon Park", 18.5362, 73.8940, 700),
        ("ZONE002", "Camp", 18.5196, 73.8553, 650),
        ("ZONE003", "Shivajinagar", 18.5308, 73.8475, 800),
        ("ZONE004", "Baner", 18.5590, 73.7860, 750),
        ("ZONE005", "Kharadi", 18.5510, 73.9360, 850),
        ("ZONE006", "Hadapsar", 18.5089, 73.9260, 900),
        ("ZONE007", "Viman Nagar", 18.5679, 73.9143, 700),
        ("ZONE008", "Hinjawadi", 18.5913, 73.7600, 1000),
    ]
    return pd.DataFrame(
        zones,
        columns=["ZoneID", "ZoneName", "Latitude", "Longitude", "Radius_Meters"],
    )


def get_location_type_probabilities(hour: int) -> list[float]:
    """Return location-type probabilities that vary by time of day."""
    if 7 <= hour < 10:
        return [0.16, 0.10, 0.28, 0.06, 0.40]
    if 12 <= hour < 15:
        return [0.15, 0.22, 0.25, 0.25, 0.13]
    if 17 <= hour < 21:
        return [0.18, 0.18, 0.07, 0.34, 0.23]
    if hour < 7 or hour >= 22:
        return [0.78, 0.08, 0.04, 0.03, 0.07]
    return [0.52, 0.14, 0.12, 0.10, 0.12]


def add_location_jitter(
    latitude: float,
    longitude: float,
    spread_meters: float,
    rng: np.random.Generator,
) -> tuple[float, float]:
    """Add a small random offset to a location, in approximate meters."""
    latitude_offset = rng.normal(0, spread_meters / 111_000)
    longitude_scale = 111_000 * np.cos(np.radians(latitude))
    longitude_offset = rng.normal(0, spread_meters / longitude_scale)
    latitude = np.clip(
        latitude + latitude_offset, LATITUDE_BOUNDS[0], LATITUDE_BOUNDS[1]
    )
    longitude = np.clip(
        longitude + longitude_offset, LONGITUDE_BOUNDS[0], LONGITUDE_BOUNDS[1]
    )
    return round(float(latitude), 6), round(float(longitude), 6)


def generate_gps_data(
    device_count: int = DEVICE_COUNT,
    pings_per_device: int = PINGS_PER_DEVICE,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """Generate repeated device pings with time- and area-based patterns."""
    rng = np.random.default_rng(seed)
    stores = create_store_locations()
    zones = create_commercial_zones()

    store_centers = list(zip(stores["Latitude"], stores["Longitude"]))
    zone_centers = list(zip(zones["Latitude"], zones["Longitude"]))
    zone_weights = np.array([1.2, 1.4, 1.2, 1.3, 1.6, 1.7, 1.5, 1.1])
    store_weights = np.array([1.4, 1.2, 1.5, 1.3, 2.0, 1.8, 1.5, 1.2, 1.0, 1.2, 1.5, 1.7])
    zone_weights /= zone_weights.sum()
    store_weights /= store_weights.sum()

    hour_weights = np.array(
        [
            0.35, 0.30, 0.25, 0.25, 0.35, 0.60, 1.20,
            2.80, 3.40, 2.80, 1.25, 1.20, 2.20, 2.80,
            2.40, 1.30, 1.40, 2.80, 3.40, 3.20, 2.60,
            1.20, 0.70, 0.45,
        ],
        dtype=float,
    )
    hour_weights /= hour_weights.sum()

    records = []
    location_types = ["Residential", "Commercial", "Office", "Shopping", "Transit"]

    for device_number in range(1, device_count + 1):
        device_id = f"DEV{device_number:06d}"
        home_center = RESIDENTIAL_AREAS[
            int(rng.integers(0, len(RESIDENTIAL_AREAS)))
        ]
        favorite_zone = int(rng.choice(len(zone_centers), p=zone_weights))
        favorite_store = int(rng.choice(len(store_centers), p=store_weights))
        favorite_office = int(rng.integers(0, len(OFFICE_AREAS)))
        favorite_transit = int(rng.integers(0, len(TRANSIT_AREAS)))

        # Distinct hours per device ensure that no complete ping rows repeat.
        hours = rng.choice(24, size=pings_per_device, replace=False, p=hour_weights)
        for hour in hours:
            location_type = str(
                rng.choice(
                    location_types,
                    p=get_location_type_probabilities(int(hour)),
                )
            )

            if location_type == "Residential":
                center = home_center
                if rng.random() >= 0.75:
                    center = RESIDENTIAL_AREAS[
                        int(rng.integers(0, len(RESIDENTIAL_AREAS)))
                    ]
                spread = 220
            elif location_type == "Commercial":
                zone_index = favorite_zone if rng.random() < 0.55 else int(
                    rng.choice(len(zone_centers), p=zone_weights)
                )
                center = zone_centers[zone_index]
                spread = 180
            elif location_type == "Shopping":
                store_index = favorite_store if rng.random() < 0.55 else int(
                    rng.choice(len(store_centers), p=store_weights)
                )
                center = store_centers[store_index]
                spread = 140
            elif location_type == "Office":
                office_index = favorite_office if rng.random() < 0.55 else int(
                    rng.integers(0, len(OFFICE_AREAS))
                )
                center = OFFICE_AREAS[office_index]
                spread = 200
            else:
                transit_index = favorite_transit if rng.random() < 0.55 else int(
                    rng.integers(0, len(TRANSIT_AREAS))
                )
                center = TRANSIT_AREAS[transit_index]
                spread = 160

            minute = int(rng.integers(0, 60))
            second = int(rng.integers(0, 60))
            timestamp = SIMULATION_DATE + pd.Timedelta(
                hours=int(hour), minutes=minute, seconds=second
            )
            latitude, longitude = add_location_jitter(
                center[0], center[1], spread, rng
            )
            records.append(
                (
                    device_id,
                    latitude,
                    longitude,
                    timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    location_type,
                )
            )

    gps_data = pd.DataFrame(
        records,
        columns=["DeviceID", "Latitude", "Longitude", "Timestamp", "Location_Type"],
    )
    return gps_data.sort_values(["Timestamp", "DeviceID"]).reset_index(drop=True)


def display_validation(gps_data: pd.DataFrame) -> None:
    """Print dataset quality checks and useful record counts."""
    timestamps = pd.to_datetime(gps_data["Timestamp"], format="%Y-%m-%d %H:%M:%S")
    print("\n--- Dataset validation ---")
    print(f"Total GPS records: {len(gps_data):,}")
    print(f"Total unique devices: {gps_data['DeviceID'].nunique():,}")
    print("\nMissing values by column:")
    print(gps_data.isna().sum().to_string())
    print(f"\nDuplicate records: {gps_data.duplicated().sum():,}")
    print(
        "Latitude range: "
        f"{gps_data['Latitude'].min():.6f} to {gps_data['Latitude'].max():.6f}"
    )
    print(
        "Longitude range: "
        f"{gps_data['Longitude'].min():.6f} to {gps_data['Longitude'].max():.6f}"
    )
    print("\nRecords by Location_Type:")
    print(gps_data["Location_Type"].value_counts().sort_index().to_string())
    print("\nRecords by hour:")
    print(timestamps.dt.hour.value_counts().sort_index().to_string())


def main() -> None:
    """Generate all three CSV files in the project's data folder."""
    data_directory = Path(__file__).resolve().parent / "data"
    data_directory.mkdir(parents=True, exist_ok=True)

    gps_data = generate_gps_data()
    gps_path = data_directory / "gps_pings.csv"
    store_path = data_directory / "store_locations.csv"
    zones_path = data_directory / "commercial_zones.csv"

    gps_data.to_csv(gps_path, index=False)
    create_store_locations().to_csv(store_path, index=False)
    create_commercial_zones().to_csv(zones_path, index=False)

    print(f"Created {gps_path} ({len(gps_data):,} records)")
    print(f"Created {store_path}")
    print(f"Created {zones_path}")
    display_validation(gps_data)


if __name__ == "__main__":
    main()
