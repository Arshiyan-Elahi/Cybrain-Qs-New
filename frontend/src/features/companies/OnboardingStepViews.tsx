import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { Checkbox } from '../../components/forms/Checkbox';
import { FieldCard } from '../../components/forms/FieldCard';
import { RadioOption } from '../../components/forms/RadioOption';
import { TextArea } from '../../components/forms/TextArea';
import { TextField } from '../../components/forms/TextField';
import {
  ONBOARDING_INDUSTRY_KEYS,
  ONBOARDING_LANGUAGE_KEYS,
  ONBOARDING_LOCATION_KEYS,
  ONBOARDING_REGULATION_KEYS,
  ONBOARDING_STEPS,
} from '../../constants/onboarding';
import type { OnboardingForm } from '../../types';
import { OnboardingFilesField } from './OnboardingFilesField';
import { OnboardingStepLayout } from './OnboardingStepLayout';
import layoutStyles from './OnboardingStepLayout.module.css';

interface StepProps {
  value: OnboardingForm;
  onChange: (next: OnboardingForm) => void;
  error?: string | null;
}

interface SummaryStepProps extends StepProps {
  onEditStep: (index: number) => void;
}

function patch(value: OnboardingForm, onChange: (next: OnboardingForm) => void, partial: Partial<OnboardingForm>) {
  onChange({ ...value, ...partial });
}

function optionLabel(prefix: string, id: string, t: (key: string) => string) {
  return t(`${prefix}.${id}`);
}

export function OnboardingCompanyStep({ value, onChange, error }: StepProps) {
  const { t } = useTranslation();
  return (
    <OnboardingStepLayout
      title={t('onboarding.company.title')}
      subtitle={t('onboarding.company.subtitle')}
      error={error}
    >
      <div className={layoutStyles.grid2}>
        <FieldCard title={t('onboarding.company.nameLabel')} hint={t('onboarding.company.nameHint')}>
          <TextField
            value={value.companyName}
            onChange={(companyName) => patch(value, onChange, { companyName })}
            placeholder={t('onboarding.company.namePlaceholder')}
            aria-label={t('onboarding.company.nameLabel')}
          />
        </FieldCard>
        <FieldCard title={t('onboarding.company.industryLabel')} hint={t('onboarding.company.industryHint')}>
          <select
            className={layoutStyles.select}
            value={value.industryKey}
            aria-label={t('onboarding.company.industryLabel')}
            onChange={(event) => patch(value, onChange, { industryKey: event.target.value })}
          >
            <option value="">{t('onboarding.company.selectPlaceholder')}</option>
            {ONBOARDING_INDUSTRY_KEYS.map((key) => (
              <option key={key} value={key}>{t(`companyData.industry.${key}`)}</option>
            ))}
          </select>
        </FieldCard>
        <FieldCard title={t('onboarding.company.locationLabel')}>
          <select
            className={layoutStyles.select}
            value={value.locationKey}
            aria-label={t('onboarding.company.locationLabel')}
            onChange={(event) => patch(value, onChange, { locationKey: event.target.value })}
          >
            <option value="">{t('onboarding.company.selectPlaceholder')}</option>
            {ONBOARDING_LOCATION_KEYS.map((key) => (
              <option key={key} value={key}>{t(`companyData.location.${key}`)}</option>
            ))}
          </select>
        </FieldCard>
        <FieldCard title={t('onboarding.company.languageLabel')}>
          <select
            className={layoutStyles.select}
            value={value.primaryLanguageKey}
            aria-label={t('onboarding.company.languageLabel')}
            onChange={(event) => patch(value, onChange, { primaryLanguageKey: event.target.value })}
          >
            {ONBOARDING_LANGUAGE_KEYS.map((key) => (
              <option key={key} value={key}>{t(`companyData.language.${key}`)}</option>
            ))}
          </select>
        </FieldCard>
      </div>
    </OnboardingStepLayout>
  );
}

export function OnboardingRegulationsStep({ value, onChange, error }: StepProps) {
  const { t } = useTranslation();
  const toggle = (id: string, checked: boolean) => {
    const regulationIds = checked
      ? [...value.regulationIds, id]
      : value.regulationIds.filter((entry) => entry !== id);
    patch(value, onChange, { regulationIds });
  };

  return (
    <OnboardingStepLayout
      title={t('onboarding.regulations.title')}
      subtitle={t('onboarding.regulations.subtitle')}
      error={error}
    >
      <FieldCard title={t('onboarding.regulations.fieldTitle')} hint={t('onboarding.regulations.fieldHint')}>
        <div className={layoutStyles.chipGrid}>
          {ONBOARDING_REGULATION_KEYS.map((key) => (
            <Checkbox
              key={key}
              label={t(`companyData.regulation.${key}`)}
              checked={value.regulationIds.includes(key)}
              onChange={(checked) => toggle(key, checked)}
            />
          ))}
        </div>
      </FieldCard>
      {value.regulationIds.length === 0 && (
        <p className={layoutStyles.empty}>{t('onboarding.regulations.empty')}</p>
      )}
    </OnboardingStepLayout>
  );
}

export function OnboardingDocumentStructureStep({ value, onChange }: StepProps) {
  const { t } = useTranslation();
  const showUpload = value.documentPathId === 'upload-sops' || value.startOptionId === 'existing-sops';

  return (
    <OnboardingStepLayout
      title={t('onboarding.documentStructure.title')}
      subtitle={t('onboarding.documentStructure.subtitle')}
    >
      <FieldCard title={t('onboarding.documentStructure.preferenceTitle')} hint={t('onboarding.documentStructure.preferenceHint')}>
        <div className={layoutStyles.optionGrid}>
          {['standard', 'from-documents', 'custom'].map((id) => (
            <RadioOption
              key={id}
              name="structure-preference"
              value={id}
              label={optionLabel('onboarding.documentStructure.preferences', id, t)}
              checked={value.structurePreferenceId === id}
              onChange={(structurePreferenceId) => patch(value, onChange, { structurePreferenceId })}
            />
          ))}
        </div>
      </FieldCard>

      {showUpload && (
        <FieldCard title={t('onboarding.documentStructure.uploadTitle')} hint={t('onboarding.documentStructure.uploadHint')}>
          <OnboardingFilesField
            files={value.uploadedDocuments}
            onChange={(uploadedDocuments) => patch(value, onChange, { uploadedDocuments })}
            addLabel={t('onboarding.files.addDocuments')}
            emptyLabel={t('onboarding.files.emptyDocuments')}
            removeLabel={t('onboarding.files.remove')}
          />
        </FieldCard>
      )}

      {value.documentPathId === 'continue-without' && (
        <p className={layoutStyles.empty}>{t('onboarding.documentStructure.withoutDocuments')}</p>
      )}

      <FieldCard title={t('onboarding.documentStructure.notesTitle')}>
        <TextArea
          value={value.documentStructureNotes}
          onChange={(documentStructureNotes) => patch(value, onChange, { documentStructureNotes })}
          placeholder={t('onboarding.documentStructure.notesPlaceholder')}
          rows={5}
        />
      </FieldCard>
    </OnboardingStepLayout>
  );
}

export function OnboardingWritingStyleStep({ value, onChange }: StepProps) {
  const { t } = useTranslation();
  return (
    <OnboardingStepLayout
      title={t('onboarding.writingStyle.title')}
      subtitle={t('onboarding.writingStyle.subtitle')}
    >
      <div className={layoutStyles.grid2}>
        <FieldCard title={t('onboarding.writingStyle.toneTitle')}>
          <div className={layoutStyles.optionGrid}>
            {['neutral', 'directive', 'explanatory'].map((id) => (
              <RadioOption
                key={id}
                name="writing-tone"
                value={id}
                label={optionLabel('onboarding.writingStyle.tones', id, t)}
                checked={value.toneId === id}
                onChange={(toneId) => patch(value, onChange, { toneId })}
              />
            ))}
          </div>
        </FieldCard>
        <FieldCard title={t('onboarding.writingStyle.formalityTitle')}>
          <div className={layoutStyles.optionGrid}>
            {['formal', 'balanced', 'accessible'].map((id) => (
              <RadioOption
                key={id}
                name="writing-formality"
                value={id}
                label={optionLabel('onboarding.writingStyle.formalities', id, t)}
                checked={value.formalityId === id}
                onChange={(formalityId) => patch(value, onChange, { formalityId })}
              />
            ))}
          </div>
        </FieldCard>
        <FieldCard title={t('onboarding.writingStyle.personTitle')}>
          <div className={layoutStyles.optionGrid}>
            {['third', 'imperative', 'mixed'].map((id) => (
              <RadioOption
                key={id}
                name="writing-person"
                value={id}
                label={optionLabel('onboarding.writingStyle.persons', id, t)}
                checked={value.personId === id}
                onChange={(personId) => patch(value, onChange, { personId })}
              />
            ))}
          </div>
        </FieldCard>
        <FieldCard title={t('onboarding.writingStyle.notesTitle')}>
          <TextArea
            value={value.writingNotes}
            onChange={(writingNotes) => patch(value, onChange, { writingNotes })}
            placeholder={t('onboarding.writingStyle.notesPlaceholder')}
            rows={5}
          />
        </FieldCard>
      </div>
    </OnboardingStepLayout>
  );
}

export function OnboardingTerminologyStep({ value, onChange }: StepProps) {
  const { t } = useTranslation();
  return (
    <OnboardingStepLayout
      title={t('onboarding.terminology.title')}
      subtitle={t('onboarding.terminology.subtitle')}
    >
      <FieldCard title={t('onboarding.terminology.listTitle')} hint={t('onboarding.terminology.listHint')}>
        <TextArea
          value={value.terminologyText}
          onChange={(terminologyText) => patch(value, onChange, { terminologyText })}
          placeholder={t('onboarding.terminology.listPlaceholder')}
          rows={8}
        />
      </FieldCard>
      <Checkbox
        label={t('onboarding.terminology.preferExisting')}
        checked={value.preferExistingTerms}
        onChange={(preferExistingTerms) => patch(value, onChange, { preferExistingTerms })}
      />
      {!value.terminologyText.trim() && (
        <p className={layoutStyles.empty}>{t('onboarding.terminology.empty')}</p>
      )}
    </OnboardingStepLayout>
  );
}

export function OnboardingOrganisationStep({ value, onChange }: StepProps) {
  const { t } = useTranslation();
  return (
    <OnboardingStepLayout
      title={t('onboarding.organisation.title')}
      subtitle={t('onboarding.organisation.subtitle')}
    >
      <div className={layoutStyles.grid2}>
        <FieldCard title={t('onboarding.organisation.departmentsTitle')} hint={t('onboarding.organisation.departmentsHint')}>
          <TextArea
            value={value.departmentsText}
            onChange={(departmentsText) => patch(value, onChange, { departmentsText })}
            placeholder={t('onboarding.organisation.departmentsPlaceholder')}
            rows={6}
          />
        </FieldCard>
        <FieldCard title={t('onboarding.organisation.rolesTitle')} hint={t('onboarding.organisation.rolesHint')}>
          <TextArea
            value={value.rolesText}
            onChange={(rolesText) => patch(value, onChange, { rolesText })}
            placeholder={t('onboarding.organisation.rolesPlaceholder')}
            rows={6}
          />
        </FieldCard>
      </div>
    </OnboardingStepLayout>
  );
}

export function OnboardingProcessesStep({ value, onChange }: StepProps) {
  const { t } = useTranslation();
  return (
    <OnboardingStepLayout
      title={t('onboarding.processes.title')}
      subtitle={t('onboarding.processes.subtitle')}
    >
      <FieldCard title={t('onboarding.processes.listTitle')} hint={t('onboarding.processes.listHint')}>
        <TextArea
          value={value.processesText}
          onChange={(processesText) => patch(value, onChange, { processesText })}
          placeholder={t('onboarding.processes.listPlaceholder')}
          rows={6}
        />
      </FieldCard>
      <FieldCard title={t('onboarding.processes.workflowTitle')}>
        <TextArea
          value={value.workflowNotes}
          onChange={(workflowNotes) => patch(value, onChange, { workflowNotes })}
          placeholder={t('onboarding.processes.workflowPlaceholder')}
          rows={5}
        />
      </FieldCard>
    </OnboardingStepLayout>
  );
}

export function OnboardingTemplatesStep({ value, onChange }: StepProps) {
  const { t } = useTranslation();
  const showTemplateUpload = value.startOptionId === 'template' || value.documentPathId === 'upload-template';

  return (
    <OnboardingStepLayout
      title={t('onboarding.templates.title')}
      subtitle={t('onboarding.templates.subtitle')}
    >
      <FieldCard title={t('onboarding.templates.preferenceTitle')}>
        <div className={layoutStyles.optionGrid}>
          {['use-uploaded', 'company-standard', 'gmp-default'].map((id) => (
            <RadioOption
              key={id}
              name="template-preference"
              value={id}
              label={optionLabel('onboarding.templates.preferences', id, t)}
              checked={value.templatePreferenceId === id}
              onChange={(templatePreferenceId) => patch(value, onChange, { templatePreferenceId })}
            />
          ))}
        </div>
      </FieldCard>

      {showTemplateUpload && (
        <FieldCard title={t('onboarding.templates.uploadTitle')} hint={t('onboarding.templates.uploadHint')}>
          <OnboardingFilesField
            files={value.uploadedTemplates}
            accept=".pdf,.docx"
            multiple={false}
            onChange={(uploadedTemplates) => patch(value, onChange, { uploadedTemplates })}
            addLabel={t('onboarding.files.addTemplate')}
            emptyLabel={t('onboarding.files.emptyTemplate')}
            removeLabel={t('onboarding.files.remove')}
          />
        </FieldCard>
      )}

      <FieldCard title={t('onboarding.templates.layoutTitle')}>
        <TextArea
          value={value.layoutNotes}
          onChange={(layoutNotes) => patch(value, onChange, { layoutNotes })}
          placeholder={t('onboarding.templates.layoutPlaceholder')}
          rows={5}
        />
      </FieldCard>
    </OnboardingStepLayout>
  );
}

export function OnboardingFormsRecordsStep({ value, onChange }: StepProps) {
  const { t } = useTranslation();
  return (
    <OnboardingStepLayout
      title={t('onboarding.formsRecords.title')}
      subtitle={t('onboarding.formsRecords.subtitle')}
    >
      <FieldCard title={t('onboarding.formsRecords.listTitle')} hint={t('onboarding.formsRecords.listHint')}>
        <TextArea
          value={value.formsText}
          onChange={(formsText) => patch(value, onChange, { formsText })}
          placeholder={t('onboarding.formsRecords.listPlaceholder')}
          rows={8}
        />
      </FieldCard>
      {!value.formsText.trim() && <p className={layoutStyles.empty}>{t('onboarding.formsRecords.empty')}</p>}
    </OnboardingStepLayout>
  );
}

export function OnboardingBusinessRulesStep({ value, onChange }: StepProps) {
  const { t } = useTranslation();
  return (
    <OnboardingStepLayout
      title={t('onboarding.businessRules.title')}
      subtitle={t('onboarding.businessRules.subtitle')}
    >
      <FieldCard title={t('onboarding.businessRules.listTitle')} hint={t('onboarding.businessRules.listHint')}>
        <TextArea
          value={value.businessRulesText}
          onChange={(businessRulesText) => patch(value, onChange, { businessRulesText })}
          placeholder={t('onboarding.businessRules.listPlaceholder')}
          rows={8}
        />
      </FieldCard>
    </OnboardingStepLayout>
  );
}

export function OnboardingRelationshipsStep({ value, onChange }: StepProps) {
  const { t } = useTranslation();
  return (
    <OnboardingStepLayout
      title={t('onboarding.relationships.title')}
      subtitle={t('onboarding.relationships.subtitle')}
    >
      <FieldCard title={t('onboarding.relationships.listTitle')} hint={t('onboarding.relationships.listHint')}>
        <TextArea
          value={value.relationshipsText}
          onChange={(relationshipsText) => patch(value, onChange, { relationshipsText })}
          placeholder={t('onboarding.relationships.listPlaceholder')}
          rows={8}
        />
      </FieldCard>
    </OnboardingStepLayout>
  );
}

export function OnboardingBestPracticesStep({ value, onChange }: StepProps) {
  const { t } = useTranslation();
  return (
    <OnboardingStepLayout
      title={t('onboarding.bestPractices.title')}
      subtitle={t('onboarding.bestPractices.subtitle')}
    >
      <FieldCard title={t('onboarding.bestPractices.listTitle')} hint={t('onboarding.bestPractices.listHint')}>
        <TextArea
          value={value.bestPracticesText}
          onChange={(bestPracticesText) => patch(value, onChange, { bestPracticesText })}
          placeholder={t('onboarding.bestPractices.listPlaceholder')}
          rows={8}
        />
      </FieldCard>
    </OnboardingStepLayout>
  );
}

export function OnboardingAiPreferencesStep({ value, onChange }: StepProps) {
  const { t } = useTranslation();
  return (
    <OnboardingStepLayout
      title={t('onboarding.aiPreferences.title')}
      subtitle={t('onboarding.aiPreferences.subtitle')}
    >
      <FieldCard title={t('onboarding.aiPreferences.levelTitle')} hint={t('onboarding.aiPreferences.levelHint')}>
        <div className={layoutStyles.optionGrid}>
          {['conservative', 'balanced', 'proactive'].map((id) => (
            <RadioOption
              key={id}
              name="ai-assist-level"
              value={id}
              label={optionLabel('onboarding.aiPreferences.levels', id, t)}
              checked={value.aiAssistLevelId === id}
              onChange={(aiAssistLevelId) => patch(value, onChange, { aiAssistLevelId })}
            />
          ))}
        </div>
      </FieldCard>
      <Checkbox
        label={t('onboarding.aiPreferences.requireVerification')}
        checked={value.requireHumanVerification}
        onChange={(requireHumanVerification) => patch(value, onChange, { requireHumanVerification })}
      />
      <FieldCard title={t('onboarding.aiPreferences.notesTitle')}>
        <TextArea
          value={value.qualityNotes}
          onChange={(qualityNotes) => patch(value, onChange, { qualityNotes })}
          placeholder={t('onboarding.aiPreferences.notesPlaceholder')}
          rows={5}
        />
      </FieldCard>
    </OnboardingStepLayout>
  );
}

function summaryValue(text: string, empty: string) {
  const trimmed = text.trim();
  return trimmed || empty;
}

export function OnboardingSummaryStep({ value, onEditStep }: SummaryStepProps) {
  const { t } = useTranslation();
  const empty = t('onboarding.summary.notProvided');
  const startLabel = t(`onboarding.start.options.${value.startOptionId}.title`, {
    defaultValue: value.startOptionId,
  });

  const sections: Array<{ stepId: string; title: string; rows: Array<[string, string]> }> = [
    {
      stepId: 'start',
      title: t('onboarding.steps.start'),
      rows: [
        [t('onboarding.summary.method'), startLabel],
        [t('onboarding.summary.documentPath'), t(`onboarding.start.paths.${value.documentPathId}`, { defaultValue: value.documentPathId })],
      ],
    },
    {
      stepId: 'company',
      title: t('onboarding.steps.company'),
      rows: [
        [t('onboarding.company.nameLabel'), summaryValue(value.companyName, empty)],
        [t('onboarding.company.industryLabel'), value.industryKey ? t(`companyData.industry.${value.industryKey}`) : empty],
        [t('onboarding.company.locationLabel'), value.locationKey ? t(`companyData.location.${value.locationKey}`) : empty],
        [t('onboarding.company.languageLabel'), value.primaryLanguageKey ? t(`companyData.language.${value.primaryLanguageKey}`) : empty],
      ],
    },
    {
      stepId: 'regulations',
      title: t('onboarding.steps.regulations'),
      rows: [[
        t('onboarding.regulations.fieldTitle'),
        value.regulationIds.length
          ? value.regulationIds.map((id) => t(`companyData.regulation.${id}`)).join(', ')
          : empty,
      ]],
    },
    {
      stepId: 'documentStructure',
      title: t('onboarding.steps.documentStructure'),
      rows: [
        [t('onboarding.documentStructure.preferenceTitle'), t(`onboarding.documentStructure.preferences.${value.structurePreferenceId}`)],
        [t('onboarding.summary.documents'), value.uploadedDocuments.length ? value.uploadedDocuments.map((file) => file.name).join(', ') : empty],
        [t('onboarding.documentStructure.notesTitle'), summaryValue(value.documentStructureNotes, empty)],
      ],
    },
    {
      stepId: 'writingStyle',
      title: t('onboarding.steps.writingStyle'),
      rows: [
        [t('onboarding.writingStyle.toneTitle'), t(`onboarding.writingStyle.tones.${value.toneId}`)],
        [t('onboarding.writingStyle.formalityTitle'), t(`onboarding.writingStyle.formalities.${value.formalityId}`)],
        [t('onboarding.writingStyle.personTitle'), t(`onboarding.writingStyle.persons.${value.personId}`)],
        [t('onboarding.writingStyle.notesTitle'), summaryValue(value.writingNotes, empty)],
      ],
    },
    {
      stepId: 'terminology',
      title: t('onboarding.steps.terminology'),
      rows: [
        [t('onboarding.terminology.listTitle'), summaryValue(value.terminologyText, empty)],
        [t('onboarding.terminology.preferExisting'), value.preferExistingTerms ? t('common.enabled') : t('common.disabled')],
      ],
    },
    {
      stepId: 'organisation',
      title: t('onboarding.steps.organisation'),
      rows: [
        [t('onboarding.organisation.departmentsTitle'), summaryValue(value.departmentsText, empty)],
        [t('onboarding.organisation.rolesTitle'), summaryValue(value.rolesText, empty)],
      ],
    },
    {
      stepId: 'processes',
      title: t('onboarding.steps.processes'),
      rows: [
        [t('onboarding.processes.listTitle'), summaryValue(value.processesText, empty)],
        [t('onboarding.processes.workflowTitle'), summaryValue(value.workflowNotes, empty)],
      ],
    },
    {
      stepId: 'templates',
      title: t('onboarding.steps.templates'),
      rows: [
        [t('onboarding.templates.preferenceTitle'), t(`onboarding.templates.preferences.${value.templatePreferenceId}`)],
        [t('onboarding.summary.templates'), value.uploadedTemplates.length ? value.uploadedTemplates.map((file) => file.name).join(', ') : empty],
        [t('onboarding.templates.layoutTitle'), summaryValue(value.layoutNotes, empty)],
      ],
    },
    {
      stepId: 'formsRecords',
      title: t('onboarding.steps.formsRecords'),
      rows: [[t('onboarding.formsRecords.listTitle'), summaryValue(value.formsText, empty)]],
    },
    {
      stepId: 'businessRules',
      title: t('onboarding.steps.businessRules'),
      rows: [[t('onboarding.businessRules.listTitle'), summaryValue(value.businessRulesText, empty)]],
    },
    {
      stepId: 'relationships',
      title: t('onboarding.steps.relationships'),
      rows: [[t('onboarding.relationships.listTitle'), summaryValue(value.relationshipsText, empty)]],
    },
    {
      stepId: 'bestPractices',
      title: t('onboarding.steps.bestPractices'),
      rows: [[t('onboarding.bestPractices.listTitle'), summaryValue(value.bestPracticesText, empty)]],
    },
    {
      stepId: 'aiPreferences',
      title: t('onboarding.steps.aiPreferences'),
      rows: [
        [t('onboarding.aiPreferences.levelTitle'), t(`onboarding.aiPreferences.levels.${value.aiAssistLevelId}`)],
        [t('onboarding.aiPreferences.requireVerification'), value.requireHumanVerification ? t('common.enabled') : t('common.disabled')],
        [t('onboarding.aiPreferences.notesTitle'), summaryValue(value.qualityNotes, empty)],
      ],
    },
  ];

  return (
    <OnboardingStepLayout
      title={t('onboarding.summary.title')}
      subtitle={t('onboarding.summary.subtitle')}
    >
      <div className={layoutStyles.summarySections}>
        {sections.map((section) => {
          const index = ONBOARDING_STEPS.findIndex((step) => step.id === section.stepId);
          return (
            <article key={section.stepId} className={layoutStyles.summaryCard}>
              <div className={layoutStyles.summaryHeader}>
                <h3>{section.title}</h3>
                <Button variant="neutral" size="xs" onClick={() => onEditStep(Math.max(0, index))}>
                  {t('onboarding.summary.edit')}
                </Button>
              </div>
              <dl className={layoutStyles.summaryRows}>
                {section.rows.map(([label, content]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{content}</dd>
                  </div>
                ))}
              </dl>
            </article>
          );
        })}
      </div>
      <p className={layoutStyles.helper}>{t('onboarding.summary.persistenceNote')}</p>
    </OnboardingStepLayout>
  );
}
