<script>
    // Shared across feed, map, and statistics views.
    import Plane from "lucide-svelte/icons/plane";
    import PawPrint from "lucide-svelte/icons/paw-print";
    import Wrench from "lucide-svelte/icons/wrench";
    import Ban from "lucide-svelte/icons/ban";
    import Flame from "lucide-svelte/icons/flame";
    import Cone from "lucide-svelte/icons/cone";
    import Skull from "lucide-svelte/icons/skull";
    import ShieldAlert from "lucide-svelte/icons/shield-alert";
    import Megaphone from "lucide-svelte/icons/megaphone";
    import Car from "lucide-svelte/icons/car";
    import TriangleAlert from "lucide-svelte/icons/triangle-alert";
    import Siren from "lucide-svelte/icons/siren";
    import Heart from "lucide-svelte/icons/heart";

    export let type;
    export let size = 16;
    export let fill = "none";
    export let color = "currentColor";

    const iconMap = {
        "Aircraft Emergency": Plane,
        "Animal Hazard": PawPrint,
        "Assist CT with Maintenance": Wrench,
        "Road Closure": Ban,
        "Car Fire": Flame,
        Construction: Cone,
        "Defective Traffic Signals": Cone,
        Fatality: Skull,
        "Hit and Run No Injuries": Car,
        JUMPER: TriangleAlert,
        "Live or Dead Animal": PawPrint,
        Maintenance: Wrench,
        "Debris From Vehicle": TriangleAlert,
        "Provide Traffic Control": ShieldAlert,
        "Report of Fire": Flame,
        "Request CalTrans Notify": ShieldAlert,
        "Road Conditions": TriangleAlert,
        "SIG Alert": Megaphone,
        SPINOUT: Car,
        "Traffic Break": ShieldAlert,
        "Traffic Collision": Car,
        "Traffic Hazard": TriangleAlert,
        "Wrong Way Driver": TriangleAlert,
        // Police
        "AUTO THEFT": Car,
        "MISD HIT/RUN": Car,
        VANDALISM: TriangleAlert,
        ROBBERY: TriangleAlert,
        "SUICIDE-THREATS": TriangleAlert,
        "DISTURBING PEACE": Megaphone,
        "REPORT OF DEATH": Skull,
        "PRISONER IN CUSTODY": ShieldAlert,
        "MENTAL CASE": TriangleAlert,
        // Fire
        MEDICAL: Heart,
        "STRUCTURE FIRE": Flame,
        "VEGETATION FIRE": Flame,
        "TRAFFIC ACCIDENT": Car,
    };

    $: Icon = iconMap[type] || Siren;
</script>

<svelte:component this={Icon} {size} {fill} {color} />
