function varargout = fg_events(varargin)
% FG_EVENTS MATLAB code for fg_events.fig
%      FG_EVENTS, by itself, creates a new FG_EVENTS or raises the existing
%      singleton*.
%
%      H = FG_EVENTS returns the handle to a new FG_EVENTS or the handle to
%      the existing singleton*.
%
%      FG_EVENTS('CALLBACK',hObject,eventData,handles,...) calls the local
%      function named CALLBACK in FG_EVENTS.M with the given input arguments.
%
%      FG_EVENTS('Property','Value',...) creates a new FG_EVENTS or raises the
%      existing singleton*.  Starting from the left, property value pairs are
%      applied to the GUI before fg_events_OpeningFcn gets called.  An
%      unrecognized property name or invalid value makes property application
%      stop.  All inputs are passed to fg_events_OpeningFcn via varargin.
%
%      *See GUI Options on GUIDE's Tools menu.  Choose "GUI allows only one
%      instance to run (singleton)".
%
% See also: GUIDE, GUIDATA, GUIHANDLES

% Edit the above text to modify the response to help fg_events

% Last Modified by GUIDE v2.5 03-Nov-2017 15:46:32

% Begin initialization code - DO NOT EDIT
gui_Singleton = 1;
gui_State = struct('gui_Name',       mfilename, ...
                   'gui_Singleton',  gui_Singleton, ...
                   'gui_OpeningFcn', @fg_events_OpeningFcn, ...
                   'gui_OutputFcn',  @fg_events_OutputFcn, ...
                   'gui_LayoutFcn',  [] , ...
                   'gui_Callback',   []);
if nargin && ischar(varargin{1})
    gui_State.gui_Callback = str2func(varargin{1});
end

if nargout
    [varargout{1:nargout}] = gui_mainfcn(gui_State, varargin{:});
else
    gui_mainfcn(gui_State, varargin{:});
end
% End initialization code - DO NOT EDIT


% --- Executes just before fg_events is made visible.
function fg_events_OpeningFcn(hObject, eventdata, handles, varargin)
    % This function has no output args, see OutputFcn.
    % hObject    handle to figure
    % eventdata  reserved - to be defined in a future version of MATLAB
    % handles    structure with handles and user data (see GUIDATA)
    % varargin   command line arguments to fg_events (see VARARGIN)

    % Choose default command line output for fg_events
    handles.output = hObject;

    % Update handles structure
    guidata(hObject, handles);

    % UIWAIT makes fg_events wait for user response (see UIRESUME)
    % uiwait(handles.figure1);
    
    % create connection object
    cnn=database('gnss_data','postgres','demostenes','org.postgresql.Driver','jdbc:postgresql://192.168.1.119:5432/');

    data = query(cnn, 'select "module" from events group by "module" order by "module" desc');
    
    modules = table2cell(data(:,1));
    modules{end+1} = 'all';
    modules = modules(end:-1:1);
    
    handles.lstModules.String = modules;
    
    data = query(cnn, 'select "node" from events group by "node" order by "node" desc');
    
    nodes = table2cell(data(:,1));
    nodes{end+1} = 'all';
    nodes = nodes(end:-1:1);
    
    handles.lstNodes.String = nodes;
    
    data = query(cnn, 'select "EventType" from events group by "EventType" order by "EventType" desc');
    
    types = table2cell(data(:,1));
    types{end+1} = 'all';
    types = types(end:-1:1);
    
    handles.lstTypes.String = types;
    
    handles.txtDS.String = datestr(datetime(now(),'ConvertFrom','datenum'),'yyyy-mm-dd HH:MM');
    handles.txtDE.String = datestr(datetime(now(),'ConvertFrom','datenum')+days(1),'yyyy-mm-dd HH:MM');
    
    UpdateTable(cnn, handles)
    
    hObj = guidata(hObject);
    hObj.cnn = cnn;
    guidata(hObject, hObj)
    
function UpdateTable(cnn, handles)
    
    sql = ['SELECT "EventDate", "EventType", "NetworkCode", "StationCode", "Year", "DOY", "Description", "module", "node" FROM events WHERE "EventDate" BETWEEN ''' handles.txtDS.String ''' AND ''' handles.txtDE.String ''' '];
    
    index = handles.lstTypes.Value;
    if ~strcmp(handles.lstTypes.String{index}, 'all')
        sql = [sql ' AND "EventType" = ''' handles.lstTypes.String{index} ''''];
    end
    
    index = handles.lstModules.Value;
    if ~strcmp(handles.lstModules.String{index}, 'all')
        sql = [sql ' AND "module" = ''' handles.lstModules.String{index} ''''];
    end
    
    index = handles.lstNodes.Value;
    if ~strcmp(handles.lstNodes.String{index}, 'all')
        sql = [sql ' AND "node" = ''' handles.lstNodes.String{index} ''''];
    end
    
    if ~isempty(strip(handles.txtNet.String))
        txt = replace(strip(handles.txtNet.String),'%', '%%');
        sql = [sql ' AND "NetworkCode" like ''' txt ''''];
    end
    
    if ~isempty(strip(handles.txtStnm.String))
        txt = replace(strip(handles.txtStnm.String),'%', '%%');
        sql = [sql ' AND "StationCode" like ''' txt ''''];
    end
    
    index = handles.lstOrder.Value;
    txt = handles.lstOrder.String{index};
    disp(txt)
    switch true
        case strcmp(txt, 'Date')
            sql = [sql ' ORDER BY "EventDate"'];
        case strcmp(txt, 'Network, Station')
            sql = [sql ' ORDER BY "NetworkCode", "StationCode"'];
        case strcmp(txt, 'Network, Station, Year, DOY')
            sql = [sql ' ORDER BY "NetworkCode", "StationCode", "Year", "DOY"'];
        case strcmp(txt, 'Year, DOY')
            sql = [sql ' ORDER BY "Year", "DOY"'];   
    end
    
    handles.figure1.Pointer = 'watch';
    data = query(cnn, sql);
    disp(sql)
    handles.tblRecords.Data = table2cell(data);
    handles.figure1.Pointer = 'arrow';
    

% --- Outputs from this function are returned to the command line.
function varargout = fg_events_OutputFcn(hObject, eventdata, handles) 
% varargout  cell array for returning output args (see VARARGOUT);
% hObject    handle to figure
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Get default command line output from handles structure
varargout{1} = handles.output;



function txtDS_Callback(hObject, eventdata, handles)
    % hObject    handle to txtDS (see GCBO)
    % eventdata  reserved - to be defined in a future version of MATLAB
    % handles    structure with handles and user data (see GUIDATA)

    % Hints: get(hObject,'String') returns contents of txtDS as text
    %        str2double(get(hObject,'String')) returns contents of txtDS as a double
    hObj = guidata(hObject);
    UpdateTable(hObj.cnn, handles)

% --- Executes during object creation, after setting all properties.
function txtDS_CreateFcn(hObject, eventdata, handles)
% hObject    handle to txtDS (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function txtDE_Callback(hObject, eventdata, handles)
    % hObject    handle to txtDE (see GCBO)
    % eventdata  reserved - to be defined in a future version of MATLAB
    % handles    structure with handles and user data (see GUIDATA)

    % Hints: get(hObject,'String') returns contents of txtDE as text
    %        str2double(get(hObject,'String')) returns contents of txtDE as a double
    hObj = guidata(hObject);
    UpdateTable(hObj.cnn, handles)

% --- Executes during object creation, after setting all properties.
function txtDE_CreateFcn(hObject, eventdata, handles)
% hObject    handle to txtDE (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function txtNet_Callback(hObject, eventdata, handles)
    % hObject    handle to txtNet (see GCBO)
    % eventdata  reserved - to be defined in a future version of MATLAB
    % handles    structure with handles and user data (see GUIDATA)

    % Hints: get(hObject,'String') returns contents of txtNet as text
    %        str2double(get(hObject,'String')) returns contents of txtNet as a double
    hObj = guidata(hObject);
    UpdateTable(hObj.cnn, handles)

% --- Executes during object creation, after setting all properties.
function txtNet_CreateFcn(hObject, eventdata, handles)
% hObject    handle to txtNet (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function txtStnm_Callback(hObject, eventdata, handles)
    % hObject    handle to txtStnm (see GCBO)
    % eventdata  reserved - to be defined in a future version of MATLAB
    % handles    structure with handles and user data (see GUIDATA)

    % Hints: get(hObject,'String') returns contents of txtStnm as text
    %        str2double(get(hObject,'String')) returns contents of txtStnm as a double

    hObj = guidata(hObject);
    UpdateTable(hObj.cnn, handles)

% --- Executes during object creation, after setting all properties.
function txtStnm_CreateFcn(hObject, eventdata, handles)
% hObject    handle to txtStnm (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end


% --- Executes on selection change in lstModules.
function lstModules_Callback(hObject, eventdata, handles)
    % hObject    handle to lstModules (see GCBO)
    % eventdata  reserved - to be defined in a future version of MATLAB
    % handles    structure with handles and user data (see GUIDATA)

    % Hints: contents = cellstr(get(hObject,'String')) returns lstModules contents as cell array
    %        contents{get(hObject,'Value')} returns selected item from lstModules
    hObj = guidata(hObject);
    UpdateTable(hObj.cnn, handles)

% --- Executes during object creation, after setting all properties.
function lstModules_CreateFcn(hObject, eventdata, handles)
% hObject    handle to lstModules (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: popupmenu controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end


% --- Executes on selection change in lstNodes.
function lstNodes_Callback(hObject, eventdata, handles)
    % hObject    handle to lstNodes (see GCBO)
    % eventdata  reserved - to be defined in a future version of MATLAB
    % handles    structure with handles and user data (see GUIDATA)

    % Hints: contents = cellstr(get(hObject,'String')) returns lstNodes contents as cell array
    %        contents{get(hObject,'Value')} returns selected item from lstNodes
    hObj = guidata(hObject);
    UpdateTable(hObj.cnn, handles)

% --- Executes during object creation, after setting all properties.
function lstNodes_CreateFcn(hObject, eventdata, handles)
% hObject    handle to lstNodes (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: popupmenu controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

function getdate(obj)
    d = datenum(obj.String,'yyyy-mm-dd HH:MM');
    newdate = uigetdate(d);
    if ~isempty(newdate)
        obj.String = datestr(datetime(newdate,'ConvertFrom','datenum'),'yyyy-mm-dd HH:MM');
    end

% --- Executes on button press in cmdDS.
function cmdDS_Callback(hObject, eventdata, handles)
    % hObject    handle to cmdDS (see GCBO)
    % eventdata  reserved - to be defined in a future version of MATLAB
    % handles    structure with handles and user data (see GUIDATA)
    hObj = guidata(hObject);
    
    getdate(handles.txtDS)
    UpdateTable(hObj.cnn, handles)
    

% --- Executes on button press in cmdDE.
function cmdDE_Callback(hObject, eventdata, handles)
    % hObject    handle to cmdDE (see GCBO)
    % eventdata  reserved - to be defined in a future version of MATLAB
    % handles    structure with handles and user data (see GUIDATA)
    hObj = guidata(hObject);
    
    getdate(handles.txtDE)
    UpdateTable(hObj.cnn, handles)


% --- Executes on selection change in lstOrder.
function lstOrder_Callback(hObject, eventdata, handles)
    % hObject    handle to lstOrder (see GCBO)
    % eventdata  reserved - to be defined in a future version of MATLAB
    % handles    structure with handles and user data (see GUIDATA)

    % Hints: contents = cellstr(get(hObject,'String')) returns lstOrder contents as cell array
    %        contents{get(hObject,'Value')} returns selected item from lstOrder
    hObj = guidata(hObject);
    UpdateTable(hObj.cnn, handles)

% --- Executes during object creation, after setting all properties.
function lstOrder_CreateFcn(hObject, eventdata, handles)
% hObject    handle to lstOrder (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: popupmenu controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end


% --- Executes on selection change in lstTypes.
function lstTypes_Callback(hObject, eventdata, handles)
    % hObject    handle to lstTypes (see GCBO)
    % eventdata  reserved - to be defined in a future version of MATLAB
    % handles    structure with handles and user data (see GUIDATA)

    % Hints: contents = cellstr(get(hObject,'String')) returns lstTypes contents as cell array
    %        contents{get(hObject,'Value')} returns selected item from lstTypes
    hObj = guidata(hObject);
    UpdateTable(hObj.cnn, handles)

% --- Executes during object creation, after setting all properties.
function lstTypes_CreateFcn(hObject, eventdata, handles)
% hObject    handle to lstTypes (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: popupmenu controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end


% --- Executes during object creation, after setting all properties.
function txtDesc_CreateFcn(hObject, eventdata, handles)
% hObject    handle to txtDesc (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called


% --- Executes when selected cell(s) is changed in tblRecords.
function tblRecords_CellSelectionCallback(hObject, eventdata, handles)
    % hObject    handle to tblRecords (see GCBO)
    % eventdata  structure with the following fields (see MATLAB.UI.CONTROL.TABLE)
    %	Indices: row and column indices of the cell(s) currently selecteds
    % handles    structure with handles and user data (see GUIDATA)
    hObj = guidata(hObject);
    
    index = eventdata.Indices;
    
    if ~isempty(index)
        row = index(1);
        col = index(2);
        hObj.selected_row = row;
        handles.txtDesc.String = handles.tblRecords.Data{row,7};
        handles.txtDetails.String = [handles.tblRecords.Data{row,3} '.' handles.tblRecords.Data{row,4}];
    else
        row = [];
        col = [];
        hObj.selected_row = 0;
    end
    
    
