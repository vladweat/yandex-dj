export type ClientChannel = "web" | "telegram";

let activeChannel: ClientChannel = "web";

export function setClientChannel(channel: ClientChannel): void {
  activeChannel = channel;
}

export function getClientChannel(): ClientChannel {
  return activeChannel;
}
