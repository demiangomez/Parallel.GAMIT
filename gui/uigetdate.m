function out = uigetdate(varargin)
% UIGETDATE  date selection dialog box
%    T = UIGETDATE(D) displays a dialog box in form of a calendar 
%    
%    UIGETDATE expects serial date number or standard MATLAB Date 
%    format (see DATESTR) as input data und returns serial date number 
%    for the selected date and time.
%
%    UIGETDATE by itself uses the current date and time as input data
%
% Example:
%         t = datestr( uigetdate('16-Aug-1974 03:00') )
% 
% See also datevec, datestr, datenum

%   version: v1.0
%   author:  Elmar Tarajan [MCommander@gmx.de]

if nargin == 0
   varargin{1} = now;
end% if

if ~ishandle(varargin{1})
   %
   datvec = datevec(varargin{1});
   %
   scr = get(0,'ScreenSize');
   h.units = 'pixels';
   h.parent = figure(h,'menubar','none', ...
            'numbertitle','off', ...
            'resize','off', ...
            'handlevisibility','on', ...
            'visible','off', ...            
            'WindowStyle','modal', ...
            'Tag','uigetdate', ...
            'position',[ (scr(3:4)- [197 199])/2 197 199 ], ...
            'keypressfcn', @figure_keypress);
        
   fp = get(h.parent,'position');
   fp = idgetnicedialoglocation(fp, get(h.parent,'Units'));
   set(h.parent,'position',fp)
   %
   pos = [5 5 0 0];
   uicontrol(h,'style','edit','position',pos+[0 0 104 26])
   uicontrol('style','slider','units','pixels','position',pos+[3 2 100 20], ...
             'sliderstep',[.0005 .0005],'min',-10,'max',10,'value',0, ...
             'callback','uigetdate(gcbo,''time'')','UserData',0)
   %
   h.style           = 'edit';
   h.fontweight      = 'bold';
   h.foregroundcolor = [.2 .2 .2];
   uicontrol(h,'enable','on','position',pos+[ 17 2 73 20],'Tag','time', ...
               'String',sprintf('%02d:%02d',datvec(4:5)),'callback',@time_callback)
   %
   % textbanners
   tmp = [2 20 101 4 ; 2 2 101 3 ; 2 2 3 22 ; 17 2 2 22 ; 88 2 2 22 ; 101 2 2 22 ];
   for i=1:6 ; uicontrol(h,'style','text','position',pos+tmp(i,:)) ; end% for
   %
   uicontrol(h,'style','edit','position',pos+[105 0 84 26],'visible','on')   
   uicontrol(h,'style','pushbutton','position',pos+[108 2 78 21],'Tag','ok', ...
               'CData',repmat(repmat([0.3:0.01:1 1:-0.01:0.3],18,1),[1 1 3]), ...
               'string','ok','Callback','uigetdate(gcbo,''ok'')')
   %
   pos = [5 32 0 0];
   uicontrol(h,'style','edit','position',pos+[0 0 189 136],'enable','inactive','Tag','cday', ...
      'UserData',datvec(3))   
   h.style      = 'pushbutton';
   h.fontweight = 'normal';
   for i=95:-19:0
      for j=0:26:156
         uicontrol(h,'position',pos+[j+3 i+2 27 20],'Enable','off', ...
                     'foregroundcolor',[.2 .2 .2],'Tag','day', ...
                     'callback','uigetdate(gcbo,''day'')')
      end% for
   end% for
   %
   tmp = {'Mon' 'Tue' 'Wed' 'Thu' 'Fri' 'Sat' 'Sun'};
   for j=0:6
      uicontrol(h,'style','text','position',pos+[j*26+4 119 25 13],'string',tmp{j+1}, ...
                  'backgroundcolor',[0.4 0.4 0.4],'foregroundcolor',[.9 .9 .9])         
   end% for
   %
   pos = [5 169 0 0];
   uicontrol(h,'style','edit','position',pos+[0 0 189 26])
   h.style = 'slider';
   uicontrol(h,'position',pos+[3 2 100 20],'sliderstep',[0.00025 1], ...
               'min',-2000,'max',2000,'Value',datvec(2), ...
               'callback','uigetdate(gcbo,''months'')')
   uicontrol(h,'position',pos+[112 2 74 20],'sliderstep',[0.00025 1], ...
               'min',0,'max',4000,'value',datvec(1), ...
               'callback','uigetdate(gcbo,''year'')')
   %
   h.style           = 'edit';
   h.enable          = 'inactive';
   h.fontweight      = 'bold';
   h.foregroundcolor = [.2 .2 .2];
   tmp = {'January' 'February' 'March' 'April' 'May' 'June' 'July' ...
          'August' 'September' 'October' 'November' 'December'};
   uicontrol(h,'position',pos+[ 17 2 73 20],'Tag','months','String',tmp{datvec(2)},'Userdata',tmp)
   uicontrol(h,'position',pos+[126 2 47 20],'Tag','year','String',num2str(datvec(1)))
   %
   % textbanners
   h.style = 'text';
   tmp = [2 20 185 4 ; 2 2 185 3 ; 2 2 3 22 ; 17 2 2 22 ; 88 2 2 22 ; ...
      101 2 13 22 ; 126 2 2 22 ; 171 2 2 22 ; 184 2 3 22];
   for i=1:9
      uicontrol(h,'position',pos+tmp(i,:))
   end% for
   %
   set(h.parent,'visible','on')
   setday(varargin{1})
   %
   set(findobj(gcf,'string',num2str(datvec(3))),'CData',geticon)
   %
   handles.time = findobj(gcf,'Tag','time');
   uicontrol(handles.time)
   uiwait
   try
      out = datenum([num2str( ...
               get(findobj(gcf,'Tag','cday'),'UserData')) '-' ...
               get(findobj(gcf,'Tag','months'),'String') '-' ...
               get(findobj(gcf,'Tag','year'),'String') ' ' ...
               get(findobj(gcf,'Tag','time'),'String') ':00']);
      delete(findobj(0,'Tag','uigetdate'))                       
   catch
      out = [];
      delete(findobj(0,'Tag','uigetdate'));
   end% try
   
   return
end% if

switch varargin{2}
   case 'months'
      h = findobj(gcbf,'Tag','months');
      months = get(h,'UserData');
      set(h,'String',months{mod(get(gcbo,'Value')-1,12)+1})
      set(findobj(gcbf,'Tag','ok'),'Enable','off')      
      % set focus to time
      f=findobj(gcbf,'Tag','time');
      uicontrol(f)
      %
   case 'year'
      set(findobj(gcbf,'Tag','year'),'String',get(gcbo,'Value'))
      set(findobj(gcbf,'Tag','ok'),'Enable','off')
      % set focus to time
      f=findobj(gcbf,'Tag','time');
      uicontrol(f)
      %
   case 'day'
      h= findobj(gcf,'Tag','day');
      set(h,'CData',[])

      set(varargin{1},'CData',geticon)
      set(findobj(gcbf,'Tag','cday'),'Userdata',get(varargin{1},'String'))
      set(findobj(gcbf,'Tag','ok'),'Enable','on')
      % set focus to time
      f=findobj(gcbf,'Tag','time');
      uicontrol(f)
      %try ; uicontrol(h(3)) ; end% try
      return
      %
   case 'time'
      try
         if toc<0.1
            step = get(gcbo,'UserData');
            set(gcbo,'UserData',step+1)
            step = floor(step*sign(get(gcbo,'value'))/2);
         else
            set(gcbo,'UserData',1)
            step = sign(get(gcbo,'value'));
            set(gcbo,'value',0)
         end% if
         %
         handles.time = findobj(gcbf,'Tag','time');
         time = sum(sscanf(get(handles.time,'String'),'%d:%d').*[60;1]);
         time = time+step;
         if time<0
            time = 1439;
         elseif time>1439
            time = 0;
         end% if
         time = sprintf('%02.f:%02.f',floor(time/60),(time/60-floor(time/60))*60);
         set(handles.time,'String',time)
         %
         tic
         % set focus to time
         f=findobj(gcbf,'Tag','time');
         uicontrol(f)
         return
      catch
         tic
      end% try
      drawnow
      % set focus to time
      f=findobj(gcbf,'Tag','time');
      uicontrol(f)
      %
   case 'ok'
      uiresume
      return
      %
end% switch
setday(['1-' get(findobj(gcbf,'Tag','months'),'String') '-' ...
             get(findobj(gcbf,'Tag','year'),'String')])
  %
  %
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
function setday(datvec)
%-------------------------------------------------------------------------------
datvec = datevec(datvec);
datvec(3) = 1;
%
day = [7 1 2 3 4 5 6];
day = day(weekday(datestr(datvec)));
%
monthend = eomday(datvec(1),datvec(2));
%
ind = [zeros(1,42-monthend-day+1) monthend:-1:1 zeros(1,day-1)];
%
enable = repmat({'on'},42,1);
enable(ind==0) = {'off'};
%
count = strrep(strrep(cellstr(num2str(ind')),' 0',''),' ','');
%
h = findobj(gcf,'Tag','day');
set(h,{'String'},count,{'Enable'},enable,'backgroundcolor',[0.7 0.7 0.7],'CData',[])
set(h(ind~=0),'backgroundcolor',[.925 .922 .9002]);
set(h(ind~=0&repmat([1 1 0 0 0 0 0],1,6)),'backgroundcolor',[1 .8 .8])
  %
  %
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
function icon = geticon
%-------------------------------------------------------------------------------
tmp = ones(15,22);
tmp(:,[1 2 3 end-2 end-1 end]) = 0;
tmp([1 2 3 end-2 end-1 end],:) = 0;
% tmp = [0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ;
%        0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ; ...
%        0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 ; ...
%        0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 ; ...
%        0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 ; ...
%        0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 ; ...
%        0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 ; ...
%        0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 ; ...
%        0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 ; ...
%        0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 ; ...
%        0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 ; ...
%        0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 ; ...
%        0 0 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 ; ...
%        0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ; ...
%        0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ];
tmp(tmp==1)=NaN;
tmp(tmp==0)=1;
icon(:,:,1) = tmp;
tmp(tmp==1)=0.25;
icon(:,:,2) = tmp;
tmp(tmp==.25)=0;
icon(:,:,3) = tmp;

%%%%%%%%%% added by DDG: Sep-28-2017 %%%%%%%%%%

function time_callback(H,E)
    if isempty(strfind(H.String,':'))
        if length(H.String) == 4
            h = str2double(H.String(1:2));
            m = str2double(H.String(3:4));
            if and(h < 24, and(m >= 0, m < 60))
                H.String = [H.String(1:2) ':' H.String(3:4)];
            else
                h = warndlg('Entered time is invalid');
                waitfor(h)
                uicontrol(H)
                return
            end
        elseif length(H.String) == 3
            h = str2double(H.String(1));
            m = str2double(H.String(2:3));
            if and(h < 9, and(m >= 0, m < 60))
                H.String = [H.String(1) ':' H.String(2:3)];
            else
                h = warndlg('Entered time is invalid');
                waitfor(h)
                uicontrol(H)
                return
            end
        else
            h = warndlg('Entered time is invalid');
            waitfor(h)
            uicontrol(H)
            return
        end
    end
    % accept change
    h=findobj(gcbf,'Tag','uigetdate');
    if strcmp(h.CurrentCharacter, char(13))
        uiresume
    end

function figure_keypress(H,E)
    if strcmp(E.Key, 'return')
        uiresume
    end

    