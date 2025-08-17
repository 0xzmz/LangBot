import { PluginCardVO } from '@/app/home/plugins/plugin-installed/PluginCardVO';
import { useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { TFunction } from 'i18next';
import {
  AudioWaveform,
  Wrench,
  Hash,
  BugIcon,
  ExternalLink,
  Ellipsis,
  Trash,
} from 'lucide-react';
import { getCloudServiceClientSync } from '@/app/infra/http';
import { PluginComponent } from '@/app/infra/entities/plugin';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

enum PluginRemoveStatus {
  WAIT_INPUT = 'WAIT_INPUT',
  REMOVING = 'REMOVING',
  ERROR = 'ERROR',
}

function getComponentList(components: PluginComponent[], t: TFunction) {
  const componentKindCount: Record<string, number> = {};

  for (const component of components) {
    const kind = component.manifest.manifest.kind;
    if (componentKindCount[kind]) {
      componentKindCount[kind]++;
    } else {
      componentKindCount[kind] = 1;
    }
  }

  const kindIconMap: Record<string, React.ReactNode> = {
    Tool: <Wrench className="w-5 h-5" />,
    EventListener: <AudioWaveform className="w-5 h-5" />,
    Command: <Hash className="w-5 h-5" />,
  };

  const componentKindList = Object.keys(componentKindCount);

  return (
    <>
      <div>{t('plugins.componentsList')}</div>
      {componentKindList.length > 0 && (
        <>
          {componentKindList.map((kind) => {
            return (
              <div
                key={kind}
                className="flex flex-row items-center justify-start gap-[0.4rem]"
              >
                {kindIconMap[kind]} {componentKindCount[kind]}
              </div>
            );
          })}
        </>
      )}

      {componentKindList.length === 0 && <div>{t('plugins.noComponents')}</div>}
    </>
  );
}

export default function PluginCardComponent({
  cardVO,
  onCardClick,
  onDeleteClick,
}: {
  cardVO: PluginCardVO;
  onCardClick: () => void;
  onDeleteClick: (cardVO: PluginCardVO) => void;
}) {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(cardVO.enabled);
  const [switchEnable, setSwitchEnable] = useState(true);

  function handleEnable(e: React.MouseEvent) {
    e.stopPropagation(); // 阻止事件冒泡
    setSwitchEnable(false);
    httpClient
      .togglePlugin(cardVO.author, cardVO.name, !enabled)
      .then(() => {
        setEnabled(!enabled);
      })
      .catch((err) => {
        toast.error(t('plugins.modifyFailed') + err.message);
      })
      .finally(() => {
        setSwitchEnable(true);
      });
  }

  return (
    <>
      <div
        className="w-[100%] h-[10rem] bg-white rounded-[10px] shadow-[0px_2px_2px_0_rgba(0,0,0,0.2)] p-[1.2rem] cursor-pointer"
        onClick={onCardClick}
      >
        <div className="w-full h-full flex flex-row items-start justify-start gap-[1.2rem]">
          <svg
            className="w-16 h-16 text-[#2288ee]"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path d="M8 4C8 2.34315 9.34315 1 11 1C12.6569 1 14 2.34315 14 4C14 4.35064 13.9398 4.68722 13.8293 5H18C18.5523 5 19 5.44772 19 6V10.1707C19.3128 10.0602 19.6494 10 20 10C21.6569 10 23 11.3431 23 13C23 14.6569 21.6569 16 20 16C19.6494 16 19.3128 15.9398 19 15.8293V20C19 20.5523 18.5523 21 18 21H4C3.44772 21 3 20.5523 3 20V6C3 5.44772 3.44772 5 4 5H8.17071C8.06015 4.68722 8 4.35064 8 4Z"></path>
          </svg>

          <div className="w-full h-full flex flex-col items-start justify-between gap-[0.6rem]">
            <div className="flex flex-col items-start justify-start">
              <div className="flex flex-col items-start justify-start">
                <div className="text-[0.7rem] text-[#666]">
                  {cardVO.author} /{' '}
                </div>
                <div className="flex flex-row items-center justify-start gap-[0.4rem]">
                  <div className="text-[1.2rem] text-black">{cardVO.name}</div>
                  <Badge variant="outline" className="text-[0.7rem]">
                    v{cardVO.version}
                  </Badge>
                  {cardVO.debug && (
                    <Badge
                      variant="outline"
                      className="text-[0.7rem] border-orange-400 text-orange-400"
                    >
                      <BugIcon className="w-4 h-4" />
                      {t('plugins.debugging')}
                    </Badge>
                  )}
                  {!cardVO.debug && (
                    <>
                      {cardVO.install_source === 'github' && (
                        <Badge
                          variant="outline"
                          className="text-[0.7rem] border-blue-400 text-blue-400"
                          onClick={(e) => {
                            e.stopPropagation();
                            window.open(
                              cardVO.install_info.github_url,
                              '_blank',
                            );
                          }}
                        >
                          {t('plugins.fromGithub')}
                          <ExternalLink className="w-4 h-4" />
                        </Badge>
                      )}
                      {cardVO.install_source === 'local' && (
                        <Badge
                          variant="outline"
                          className="text-[0.7rem] border-green-400 text-green-400"
                        >
                          {t('plugins.fromLocal')}
                        </Badge>
                      )}
                      {cardVO.install_source === 'marketplace' && (
                        <Badge
                          variant="outline"
                          className="text-[0.7rem] border-purple-400 text-purple-400"
                          onClick={(e) => {
                            e.stopPropagation();
                            window.open(
                              getCloudServiceClientSync().getPluginMarketplaceURL(
                                cardVO.author,
                                cardVO.name,
                              ),
                              '_blank',
                            );
                          }}
                        >
                          {t('plugins.fromMarketplace')}
                          <ExternalLink className="w-4 h-4" />
                        </Badge>
                      )}
                    </>
                  )}
                </div>
              </div>

              <div className="text-[0.8rem] text-[#666] line-clamp-2">
                {cardVO.description}
              </div>
            </div>

            <div className="w-full flex flex-row items-start justify-start gap-[0.6rem]">
              {getComponentList(cardVO.components, t)}
            </div>
          </div>

          <div className="flex flex-col items-center justify-between h-full">
            <div className="flex items-center justify-center">
              <Switch
                className="cursor-pointer"
                checked={enabled}
                onClick={(e) => handleEnable(e)}
                disabled={!switchEnable}
              />
            </div>

            <div className="flex items-center justify-center">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost">
                    <Ellipsis className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem
                    className="flex flex-row items-center justify-start gap-[0.4rem] cursor-pointer"
                    onClick={(e) => {
                      onDeleteClick(cardVO);
                      e.stopPropagation();
                    }}
                  >
                    <Trash className="w-4 h-4" />
                    <span>{t('plugins.delete')}</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
