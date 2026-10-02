"use strict";
// (1–5) and stores [construction cost, seasonal revenue].
const TRADE_BUILDINGS={
  gold_mine:{n:"Gold Mine",l:[[750,50],[1250,100],[2000,175],[3000,275],[4500,400]]},
  copper_mine:{n:"Copper Mine",l:[[650,50],[1100,100],[1750,150],[2750,250],[4000,350]]},
  silver_mine:{n:"Silver Mine",l:[[750,60],[1250,125],[2000,200],[3000,300],[4500,425]]},
  mithril_mine:{n:"Mithril Mine",l:[[1000,75],[1750,150],[2750,250],[4000,400],[6000,600]]},
  gem_mine:{n:"Gem Mine",l:[[850,75],[1400,150],[2250,250],[3500,375],[5000,500]]},
  iron_mine:{n:"Iron Mine",l:[[650,50],[1100,100],[1750,175],[2750,275],[4000,375]]},
  exotic_animal_pen:{n:"Exotic Animal Pen",l:[[850,60],[1400,125],[2250,200],[3500,325],[5000,450]]},
  grain_farm:{n:"Grain Farm",l:[[500,50],[900,100],[1500,150],[2250,225],[3500,325]]},
  goat_pen:{n:"Goat Pen",l:[[500,50],[900,100],[1500,150],[2250,225],[3500,325]]},
  sheep_pen:{n:"Sheep Pen",l:[[500,50],[900,100],[1500,150],[2250,225],[3500,325]]},
  healing_herb_garden:{n:"Healing Herb Garden",l:[[600,60],[1000,125],[1750,200],[2750,300],[4000,400]]},
  timber_yard:{n:"Timber Yard",l:[[500,40],[850,75],[1400,125],[2200,175],[3250,275]]},
  fur_trappers_camp:{n:"Fur Trapper's Camp",l:[[600,50],[1000,100],[1650,150],[2500,225],[3750,325]]},
  winery:{n:"Winery",l:[[750,60],[1250,125],[2000,200],[3000,300],[4500,400]]},
  fishing_jetties:{n:"Fishing Jetties",l:[[600,50],[1000,100],[1650,150],[2500,225],[3750,325]]},
  salt_mine:{n:"Salt Mine",l:[[650,60],[1100,125],[1750,200],[2750,275],[4000,375]]},
  spice_trader:{n:"Spice Trader",l:[[750,65],[1250,125],[2000,200],[3000,300],[4500,425]]},
  stone_quarry:{n:"Stone Quarry",l:[[500,40],[850,75],[1400,125],[2200,175],[3250,250]]},
  horse_stables:{n:"Horse Stables",l:[[750,60],[1250,125],[2000,200],[3000,275],[4500,375]]},
  blacksmith:{n:"Blacksmith",note:"Units recruited here (Barracks required) start with +1 chevron per level",l:[[750,0],[1250,0],[2000,0],[3000,0],[4500,0]]},
  slavers_market:{n:"Slavers' Market",l:[[500,40],[850,75],[1400,125],[2200,200],[3250,300]]},
  pipeweed_fields:{n:"Pipe Weed Fields",l:[[750,65],[1250,125],[2000,200],[3000,300],[4500,425]]}
};
