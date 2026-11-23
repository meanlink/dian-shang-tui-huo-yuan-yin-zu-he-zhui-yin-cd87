import {request} from '../api.js';
import {bindForm, errorBox, flash} from '../ui.js';

export const text = (key, label, min = 2) => `<label>${label}<input name="${key}" minlength="${min}" required></label>`;
export const number = (key, label, minimum = 0, maximum = 10000000) => `<label>${label}<input name="${key}" type="number" min="${minimum}" max="${maximum}" step="1" required></label>`;
export const action = (title, fields, button, url) => `<form class="vendor-form form-stack" data-action="${url}">
  <h3>${title}</h3><div>${fields.join('')}</div>${errorBox}<button type="submit">${button}</button></form>`;

export function wire(root, refresh) {
  for (const form of root.querySelectorAll('.vendor-form')) {
    bindForm(form, async values => {
      const body = Object.fromEntries(values);
      for (const input of form.querySelectorAll('input[type=number]')) body[input.name] = Number(body[input.name]);
      let url = form.dataset.action;
      if (url.includes('$shipment')) {
        url = url.replace('$shipment', encodeURIComponent(body.shipment_id));
        delete body.shipment_id;
      }
      if (body.acknowledged_ref === '') delete body.acknowledged_ref;
      await request(url, 'POST', body);
      await refresh(root);
      flash('供方协作记录已保存');
    });
  }
}
