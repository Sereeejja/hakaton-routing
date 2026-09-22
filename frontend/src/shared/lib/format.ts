const skillLabels: Record<string, string> = {
  connection: "Подключение",
  local: "Локальные работы",
  emergency: "Авария",
};

export function formatSkill(skill: string): string {
  return skillLabels[skill] ?? skill;
}

const transportLabels: Record<string, string> = {
  car: "автомобиль",
  walk: "пешком",
  bicycle: "велосипед",
  public_transit: "общественный транспорт",
};

export function formatTransport(transport: string): string {
  return transportLabels[transport] ?? transport;
}

export function formatClock(totalMinutes: number): string {
  const normalized = Math.max(0, Math.round(totalMinutes));
  const hours = Math.floor(normalized / 60).toString().padStart(2, "0");
  const minutes = (normalized % 60).toString().padStart(2, "0");
  return `${hours}:${minutes}`;
}

export function formatDistance(distanceKm: number): string {
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: distanceKm < 10 ? 1 : 0,
    maximumFractionDigits: 1,
  }).format(distanceKm);
}

export function shortAddress(address: string, length = 38): string {
  return address.length > length ? `${address.slice(0, length - 1)}…` : address;
}

export function coordinateLabel(latitude: number, longitude: number): string {
  return `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
}
