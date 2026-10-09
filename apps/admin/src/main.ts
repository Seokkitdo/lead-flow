import { mount } from 'svelte';
import CrmApp from '@leadflow/crm';
import '@leadflow/ui/theme.css';
mount(CrmApp, { target: document.getElementById('app')! });
