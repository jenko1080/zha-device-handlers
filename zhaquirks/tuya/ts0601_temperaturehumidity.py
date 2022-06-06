"""Tuya temp and humidity sensor with e-ink screen."""

from typing import Dict

from zigpy.profiles import zha
from zigpy.quirks import CustomDevice
import zigpy.types as t
from zigpy.zcl.clusters.general import (
    Basic,
    Groups,
    Ota,
    PowerConfiguration,
    Scenes,
    Time,
)
from zigpy.zcl.clusters.measurement import RelativeHumidity, TemperatureMeasurement

from zhaquirks import Bus
from zhaquirks.const import (
    DEVICE_TYPE,
    ENDPOINTS,
    INPUT_CLUSTERS,
    MODELS_INFO,
    OUTPUT_CLUSTERS,
    PROFILE_ID,
    SKIP_CONFIGURATION,
)
from zhaquirks.tuya import (
    TuyaLocalCluster,
    TuyaManufClusterAttributes,
    TuyaNewManufCluster,
)
from zhaquirks.tuya.mcu import DPToAttributeMapping, TuyaDPType

# NOTES:
# The data comes in as a string on cluster, if there is nothing set up you may see these lines in the logs:
# Unknown message (b'19830100a40102000400000118') on cluster 61184: unknown endpoint or cluster id: 'No cluster ID 0xef00 on (a4:c1:38:d0:18:8b:64:aa, 1)'
#                                          28.0 degrees
# Unknown message (b'19840100a5020200040000022c') on cluster 61184: unknown endpoint or cluster id: 'No cluster ID 0xef00 on (a4:c1:38:d0:18:8b:64:aa, 1)'
#                                          55.6% humid
# Unknown message (b'19850100a60402000400000064') on cluster 61184: unknown endpoint or cluster id: 'No cluster ID 0xef00 on (a4:c1:38:d0:18:8b:64:aa, 1)'
#                                          100% battery

# Constants that map to the string values in the previously `Unknown message` lines.
TUYA_TEMPERATURE_ATTR = 0x0201  # [0, 0, 0, 237] temperature in decidegree
TUYA_HUMIDITY_ATTR = 0x0202  # [0, 0, 2, 64] humidity
TUYA_BATTERY_ATTR = 0x0204  # [0, 0, 0, 100] battery


class TuyaPowerConfigurationCluster2AAA(PowerConfiguration, TuyaLocalCluster):
    """PowerConfiguration cluster for battery-operated TRVs with 2 AAA."""

    BATTERY_SIZES = 0x0031
    BATTERY_QUANTITY = 0x0033
    BATTERY_RATED_VOLTAGE = 0x0034

    _CONSTANT_ATTRIBUTES = {
        BATTERY_SIZES: 4,
        BATTERY_QUANTITY: 2,
        BATTERY_RATED_VOLTAGE: 15,
    }


class TuyaTemperatureMeasurement(TemperatureMeasurement, TuyaLocalCluster):
    """Tuya local TemperatureMeasurement cluster."""


class TuyaRelativeHumidity(RelativeHumidity, TuyaLocalCluster):
    """Tuya local RelativeHumidity cluster."""


class TemperatureHumidityManufCluster(TuyaNewManufCluster):
    """Tuya Manufacturer Cluster with Temperature and Humidity data points."""

    attributes = TuyaManufClusterAttributes.attributes.copy()
    attributes.update(
        {
            TUYA_TEMPERATURE_ATTR: ("temperature", t.uint32_t, True),
            TUYA_HUMIDITY_ATTR: ("humidity", t.uint32_t, True),
            TUYA_BATTERY_ATTR: ("battery", t.uint8_t, True),
        }
    )

    dp_to_attribute: Dict[int, DPToAttributeMapping] = {
        1: DPToAttributeMapping(
            TuyaTemperatureMeasurement.ep_attribute,
            "measured_value",
            dp_type=TuyaDPType.VALUE,
            converter=lambda x: x * 10,  # decidegree to centidegree
        ),
        2: DPToAttributeMapping(
            TuyaRelativeHumidity.ep_attribute,
            "measured_value",
            dp_type=TuyaDPType.VALUE,
            converter=lambda x: x * 10,  # decipercent to centipercent
        ),
        4: DPToAttributeMapping(
            TuyaPowerConfigurationCluster2AAA.ep_attribute,
            "battery_percentage_remaining",
            dp_type=TuyaDPType.VALUE,
            converter=lambda x: x * 2,  # double reported percentage
        ),
    }

    data_point_handlers = {
        1: "_dp_2_attr_update",
        2: "_dp_2_attr_update",
        4: "_dp_2_attr_update",
    }


class TuyaTempHumiditySensor(CustomDevice):
    """Custom device representing tuya temp and humidity sensor with e-ink screen."""

    def __init__(self, *args, **kwargs):
        """Init device."""

        self.temperature_bus = Bus()
        self.humidity_bus = Bus()
        self.battery_bus = Bus()

        super().__init__(*args, **kwargs)

    signature = {
        # <SimpleDescriptor endpoint=1, profile=260, device_type=81
        # device_version=1
        # input_clusters=[4, 5, 61184, 0]
        # output_clusters=[25, 10]>
        MODELS_INFO: [("_TZE200_bjawzodf", "TS0601")],
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.SMART_PLUG,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    TemperatureHumidityManufCluster.cluster_id,
                ],
                OUTPUT_CLUSTERS: [Ota.cluster_id, Time.cluster_id],
            }
        },
    }

    replacement = {
        SKIP_CONFIGURATION: True,
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.TEMPERATURE_SENSOR,
                INPUT_CLUSTERS: [
                    TemperatureHumidityManufCluster,  # Single bus for temp, humidity, and battery
                    TuyaTemperatureMeasurement,
                    TuyaRelativeHumidity,
                    TuyaPowerConfigurationCluster2AAA,
                ],
                OUTPUT_CLUSTERS: [Ota.cluster_id, Time.cluster_id],
            }
        },
    }
