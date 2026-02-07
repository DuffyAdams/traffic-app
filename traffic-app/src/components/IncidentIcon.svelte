<script>
    import {
        Plane,
        PawPrint,
        Wrench,
        Ban,
        Flame,
        HardHat,
        Cone,
        Skull,
        CarFront,
        UserX,
        Hammer,
        Box,
        ShieldAlert,
        PhoneCall,
        Signpost,
        Megaphone,
        RotateCcw,
        Hand,
        Car,
        TriangleAlert,
        ArrowLeftRight,
        Siren,
        Heart,
    } from "lucide-svelte";

    export let type;
    export let size = 16;
    export let fill = "none";

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

<svelte:component this={Icon} {size} {fill} />
