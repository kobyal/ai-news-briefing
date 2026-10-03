/** WhatsApp "send to…" deep link. Shared by story pages (ShareButton) and
 *  event cards — WhatsApp groups are where Israeli devs pass meetups around. */
export function whatsappShareUrl(text: string): string {
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}
