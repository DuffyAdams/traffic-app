<script>
    import Plane from "lucide-svelte/icons/plane";
    import PawPrint from "lucide-svelte/icons/paw-print";
    import Wrench from "lucide-svelte/icons/wrench";
    import Ban from "lucide-svelte/icons/ban";
    import Flame from "lucide-svelte/icons/flame";
    import HardHat from "lucide-svelte/icons/hard-hat";
    import Cone from "lucide-svelte/icons/cone";
    import Skull from "lucide-svelte/icons/skull";
    import CarFront from "lucide-svelte/icons/car-front";
    import UserX from "lucide-svelte/icons/user-x";
    import Hammer from "lucide-svelte/icons/hammer";
    import Box from "lucide-svelte/icons/box";
    import ShieldAlert from "lucide-svelte/icons/shield-alert";
    import PhoneCall from "lucide-svelte/icons/phone-call";
    import Signpost from "lucide-svelte/icons/signpost";
    import Megaphone from "lucide-svelte/icons/megaphone";
    import RotateCcw from "lucide-svelte/icons/rotate-ccw";
    import Hand from "lucide-svelte/icons/hand";
    import Car from "lucide-svelte/icons/car";
    import TriangleAlert from "lucide-svelte/icons/triangle-alert";
    import ArrowLeftRight from "lucide-svelte/icons/arrow-left-right";
    import Siren from "lucide-svelte/icons/siren";
    import Heart from "lucide-svelte/icons/heart";

    export let type;
    export let size = 16;
    export let fill = "none";
    export let color = "#ffffff";

    const iconMap = {
        "Aircraft Emergency": Plane,
        "Animal Hazard": PawPrint,
        "Assist CT with Maintenance": Wrench,
        "Road Closure": Ban,
        "Car Fire": Flame,
        Construction: HardHat,
        "Defective Traffic Signals": Cone,
        Fatality: Skull,
        "Hit and Run No Injuries": CarFront,
        JUMPER: UserX,
        "Live or Dead Animal": PawPrint,
        Maintenance: Hammer,
        "Debris From Vehicle": Box,
        "Provide Traffic Control": ShieldAlert,
        "Report of Fire": Flame,
        "Request CalTrans Notify": PhoneCall,
        "Road Conditions": Signpost,
        "SIG Alert": Megaphone,
        SPINOUT: RotateCcw,
        "Traffic Break": Hand,
        "Traffic Collision": Car,
        "Traffic Hazard": TriangleAlert,
        "Wrong Way Driver": ArrowLeftRight,
        // Police
        "AUTO THEFT": Car,
        "MISD HIT/RUN": CarFront,
        VANDALISM: TriangleAlert,
        ROBBERY: TriangleAlert,
        "SUICIDE-THREATS": UserX,
        "DISTURBING PEACE": Megaphone,
        "REPORT OF DEATH": Skull,
        "PRISONER IN CUSTODY": UserX,
        "MENTAL CASE": UserX,
        // Fire
        MEDICAL: Heart,
        "STRUCTURE FIRE": Flame,
        "VEGETATION FIRE": Flame,
        "TRAFFIC ACCIDENT": Car,
    };

    $: Icon = iconMap[type] || Siren;
</script>

<svelte:component this={Icon} {size} {fill} {color} />
