# WhatsApp (statuses and the WhatsApp door)

Evolution is one of the bakery WhatsApp's linked devices. The link lasts until:
- someone removes it on the phone (WhatsApp → Settings → Linked devices),
- the primary phone is unused for more than 14 days (WhatsApp then logs linked devices out),
- or WhatsApp ends the session itself.

You'll notice it: the menu bar shows "WhatsApp ✗" and a "WhatsApp disconnected" notification.
Statuses and the WhatsApp door stop until it's linked again.

## Link again (2 minutes, with the bakery's phone)

1. Turn PostForge on.
2. Run `./scripts/link-whatsapp.sh`. It opens a QR code, and does nothing if WhatsApp is still linked.
3. On the bakery's phone: WhatsApp → Settings → **Linked devices** → **Link a device** → scan the code
   (within 3 minutes).
4. The menu bar shows WhatsApp ✓ again.

Never copy the WhatsApp session from one Mac to another: link each Mac as its own device
(DEPLOY-M1.md §8).

WhatsApp also documents automatic disconnection after 30 days of linked-device inactivity. This is separate from PostForge’s 30-day file-history setting. See [linked devices](https://faq.whatsapp.com/378279804439436/).
