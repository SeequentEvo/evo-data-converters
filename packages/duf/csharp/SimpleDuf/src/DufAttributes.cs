using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Xml;
using Deswik.Core.Structures;
using Deswik.Duf;
using Deswik.Entities;
using Deswik.Entities.Cad;

namespace DufWrapper
{
    public enum AttributeType
    {
        String,
        Integer,
        Double,
        DateTime
    }

    public class DufAttributes : IReadOnlyList<DufAttributes.Attribute>
    {
        public const string DeswikStandardAttributePrefix = "_dw_Attribute";
        public const string DeswikVertexAttributePrefix = "_dw_VertexAttribute";

        private Layer _layer;
        private string _namePrefix;
        private readonly AttributesType _type;
        private string _countPropertyName;

        private Dictionary<string, int> _nameToIndexMap = new Dictionary<string, int>();

        public Attribute this[int index] => GetAttributeFromXProperties(index);

        public DufAttributes(Layer layer, AttributesType type = AttributesType.Standard, string namePrefix = null)
        {
            _layer = layer;
            _type = type;

            if (namePrefix is null)
            {
                _namePrefix = type == AttributesType.Standard ? DeswikStandardAttributePrefix : DeswikVertexAttributePrefix;
            }

            _countPropertyName = _namePrefix + "Count";
        }

        private XProperties EnsureXProperties()
        {
            return DufDocument.EnsureXProperties(_layer);
        }

        public int Count
        {
            get
            {
                var countProp = _layer.XProperties is null ? null : DufDocument.XPropertyGet(_layer.XProperties, _countPropertyName);

                if (countProp != null)
                {
                    int count = -1;

                    if ((countProp.Value?.Any() ?? false))
                    {
                        count = countProp.Value[0].ValueInt32 ?? 0;
                    }

                    if (count >= 0)
                    {
                        return count;
                    }
                }

                return 0;
            }

            private set
            {
                var xprops = EnsureXProperties();

                DufDocument.XPropertySet(xprops, _countPropertyName, value);
            }
        }

        private Attribute GetAttributeFromXProperties(int i)
        {
            Attribute attr = null;

            if (i >= 0 && i < Count)
            {
                var attributePropertyNames = AttributePropertyNames.GetAttributePropertyNames(_namePrefix, i);

                attr = Attribute.GetFromXProperties(_layer?.XProperties, attributePropertyNames);
            }

            return attr;
        }

        public int FindNameIndex(string name)
        {
            var count = Count;

            if (_nameToIndexMap.Count != count)
            {
                for (int i = 0; i < count; ++i)
                {
                    var propertyNames = AttributePropertyNames.GetAttributePropertyNames(_namePrefix, i);
                    var xprop = DufDocument.XPropertyGet(_layer?.XProperties, propertyNames.GetPropertyName(AttributePropertyNames.Name), false);

                    if ((xprop?.Value?.Any() ?? false) && !string.IsNullOrWhiteSpace(xprop.Value[0].ValueString))
                    {
                        var attrName = xprop.Value[0].ValueString;
                        _nameToIndexMap[attrName] = i;
                    }
                }
            }

            if (!_nameToIndexMap.TryGetValue(name, out int found))
            {
                found = -1;
            }

            return found;
        }

        public bool HasAttribute(string name)
        {
            return FindNameIndex(name) != -1;
        }

        public Attribute FindName(string name)
        {
            var found = FindNameIndex(name);

            return found < 0 ? null : this[found];
        }

        public bool Add(bool replaceExisting, params Attribute[] attributes)
        {
            bool added = false;

            foreach (var attribute in attributes)
            {
                if (!string.IsNullOrWhiteSpace(attribute?.Name))
                {
                    var index = FindNameIndex(attribute.Name);

                    if (index < 0 || replaceExisting)
                    {
                        var xprops = EnsureXProperties();

                        if (xprops != null)
                        {
                            if (index < 0)
                            {
                                index = Count++;
                            }

                            var propertyNames = AttributePropertyNames.GetAttributePropertyNames(_namePrefix, index);

                            _nameToIndexMap[attribute.Name] = index;
                            attribute.SetInXProperties(xprops, propertyNames);
                            added = true;
                        }
                    }
                }
            }

            return added;
        }

        public bool Add(params Attribute[] attributes)
        {
            return Add(false, attributes);
        }

        public bool Replace(params Attribute[] attributes)
        {
            return Add(true, attributes);
        }

        internal void RemoveAt(int index)
        {
            if (index >= 0)
            {
                var count = Count;

                if (index < count)
                {
                    AttributePropertyNames propertyNames;
                    var attr = this[index];

                    _nameToIndexMap.Remove(attr.Name);

                    for (int from = index + 1; from < count; ++from, ++index)
                    {
                        propertyNames = AttributePropertyNames.GetAttributePropertyNames(_namePrefix, index);
                        attr = this[from];

                        attr.SetInXProperties(_layer.XProperties, propertyNames);

                        _nameToIndexMap[attr.Name] = index;
                    }

                    Count = index;

                    propertyNames = AttributePropertyNames.GetAttributePropertyNames(_namePrefix, index);

                    Attribute.RemoveFromXProperties(_layer.XProperties, propertyNames);
                }
            }
        }

        public void Remove(params string[] names)
        {
            foreach (var name in names)
            {
                RemoveAt(FindNameIndex(name));
            }
        }

        public IEnumerator<Attribute> GetEnumerator()
        {
            return new AttributeEnumerator(this);
        }

        IEnumerator IEnumerable.GetEnumerator()
        {
            return GetEnumerator();
        }

        public class AttributeEnumerator : IEnumerator<Attribute>
        {
            private bool disposedValue;

            private DufAttributes _attributes;

            private int _position = -1;

            internal AttributeEnumerator(DufAttributes attributes)
            {
                _attributes = attributes;
            }

            public Attribute Current => _attributes[_position];

            object IEnumerator.Current => Current;

            public bool MoveNext()
            {
                return ++_position < _attributes.Count;
            }

            public void Reset()
            {
                _position = -1;
            }

            protected virtual void Dispose(bool disposing)
            {
                if (!disposedValue)
                {
                    if (disposing)
                    {
                        // TODO: dispose managed state (managed objects)
                    }

                    // TODO: free unmanaged resources (unmanaged objects) and override finalizer
                    // TODO: set large fields to null
                    disposedValue = true;
                }
            }

            // // TODO: override finalizer only if 'Dispose(bool disposing)' has code to free unmanaged resources
            // ~AttributeEnumerator()
            // {
            //     // Do not change this code. Put cleanup code in 'Dispose(bool disposing)' method
            //     Dispose(disposing: false);
            // }

            public void Dispose()
            {
                // Do not change this code. Put cleanup code in 'Dispose(bool disposing)' method
                Dispose(disposing: true);
                GC.SuppressFinalize(this);
            }
        }

        internal class AttributePropertyNames
        {
            public const string Name = "Name";
            public const string Type = "Type";
            public const string DefaultValue = "DefaultValue";
            public const string DisplayInProperties = "DisplayInProperties";
            public const string Group = "Group";
            public const string Prompt = "Prompt";
            public const string ValuesList = "ValuesList";
            public const string LimitToList = "LimitToList";
            public const string LookupList = "LookupList";
            public const string Description = "Description";
            public const string Format = "Format";
            public const string Required = "Required";
            public const string Locked = "Locked";
            public const string DisplayMode = "DisplayMode";
            public const string WeightField = "WeightField";
            public const string AttributeCount = "AttributeCount";

            private static Dictionary<string, Dictionary<int, AttributePropertyNames>> _propertyNameCache = new Dictionary<string, Dictionary<int, AttributePropertyNames>>();

            private Dictionary<string, string> _propertyNames = new Dictionary<string, string>();

            private AttributePropertyNames(string namePrefix, int i)
            {
                string indexedPrefix = $"{namePrefix}[{i}].";

                foreach (var suffix in Attribute.PropertyNamesAndDefaults.Keys)
                {
                    _propertyNames[suffix] = indexedPrefix + suffix;
                }
            }

            public static AttributePropertyNames GetAttributePropertyNames(string namePrefix, int i)
            {
                if (!_propertyNameCache.TryGetValue(namePrefix, out var indexCache))
                {
                    indexCache = new Dictionary<int, AttributePropertyNames>();
                    _propertyNameCache[namePrefix] = indexCache;
                }

                if (!indexCache.TryGetValue(i, out var found))
                {
                    found = new AttributePropertyNames(namePrefix, i);
                    indexCache[i] = found;
                }

                return found;
            }

            public string GetPropertyName(string property)
            {
                return _propertyNames[property];
            }
        }

        public class Attribute
        {
            [Flags]
            public enum DisplayModeConstants
            {
                None = 0,
                Sum = 1,
                Average = 2,
                Maximum = 4,
                Minimum = 8,
                Count = 0x10,
                WeightedAverage = 0x20
            }

            // Attribute property names

            public static Dictionary<string, object> PropertyNamesAndDefaults = new Dictionary<string, object>()
            {
                { AttributePropertyNames.Name, "" },
                { AttributePropertyNames.Type, NameFromType(AttributeType.String) },
                { AttributePropertyNames.DefaultValue, "" },
                { AttributePropertyNames.DisplayInProperties, true },
                { AttributePropertyNames.Group, "" },
                { AttributePropertyNames.Prompt, false },
                { AttributePropertyNames.ValuesList, "" },
                { AttributePropertyNames.LimitToList, false },
                { AttributePropertyNames.LookupList, "" },
                { AttributePropertyNames.Description, "" },
                { AttributePropertyNames.Format, "" },
                { AttributePropertyNames.Required, false },
                { AttributePropertyNames.Locked, false },
                { AttributePropertyNames.DisplayMode, DisplayModeConstants.None },
                { AttributePropertyNames.WeightField, "" },
            };

            private Dictionary<string, object> _propertyValues;

            private static string NameFromType(AttributeType type) => Enum.GetName(typeof(AttributeType), type);

            private static AttributeType TypeFromName(string name) => (AttributeType)Enum.Parse(typeof(AttributeType), name);

            public string Name
            {
                get => GetStringOrDefault(AttributePropertyNames.Name);
                set => _propertyValues[AttributePropertyNames.Name] = value;
            }

            public AttributeType Type
            {
                get => TypeFromName(GetStringOrDefault(AttributePropertyNames.Type));
                set => _propertyValues[AttributePropertyNames.Type] = NameFromType(value);
            }

            public string DefaultValue
            {
                get => GetStringOrDefault(AttributePropertyNames.DefaultValue);
                set => _propertyValues[AttributePropertyNames.DefaultValue] = value;
            }

            public bool DisplayInProperties
            {
                get => GetBoolOrDefault(AttributePropertyNames.DisplayInProperties);

                set => _propertyValues[AttributePropertyNames.DisplayInProperties] = value;
            }

            public string Group
            {
                get => GetStringOrDefault(AttributePropertyNames.Group);

                set => _propertyValues[AttributePropertyNames.Group] = value;
            }

            public bool Prompt
            {
                get => GetBoolOrDefault(AttributePropertyNames.Prompt);

                set => _propertyValues[AttributePropertyNames.Prompt] = value;
            }

            public string ValuesList
            {
                get => GetStringOrDefault(AttributePropertyNames.ValuesList);

                set => _propertyValues[AttributePropertyNames.ValuesList] = value;
            }

            public bool LimitToList
            {
                get => GetBoolOrDefault(AttributePropertyNames.LimitToList);

                set => _propertyValues[AttributePropertyNames.LimitToList] = value;
            }

            public string LookupList
            {
                get => GetStringOrDefault(AttributePropertyNames.LookupList);

                set => _propertyValues[AttributePropertyNames.LookupList] = value;
            }

            public string Description
            {
                get => GetStringOrDefault(AttributePropertyNames.Description);

                set => _propertyValues[AttributePropertyNames.Description] = value;
            }

            public string Format
            {
                get => GetStringOrDefault(AttributePropertyNames.Format);

                set => _propertyValues[AttributePropertyNames.Format] = value;
            }

            public bool Required
            {
                get => GetBoolOrDefault(AttributePropertyNames.Required);

                set => _propertyValues[AttributePropertyNames.Required] = value;
            }

            public bool Locked
            {
                get => GetBoolOrDefault(AttributePropertyNames.Locked);

                set => _propertyValues[AttributePropertyNames.Locked] = value;
            }

            public DisplayModeConstants DisplayMode
            {
                get => (DisplayModeConstants)GetIntOrDefault(AttributePropertyNames.DisplayMode);

                set => _propertyValues[AttributePropertyNames.DisplayMode] = (int)value;
            }

            public string WeightField
            {
                get => GetStringOrDefault(AttributePropertyNames.WeightField);

                set => _propertyValues[AttributePropertyNames.WeightField] = value;
            }

            public Attribute()
            {
                _propertyValues = new Dictionary<string, object>(PropertyNamesAndDefaults);
            }

            public Attribute(
                string name,
                AttributeType type,
                object defaultvalue,
                bool displayInProps,
                string group,
                bool prompt,
                string valuesList,
                string description,
                string format,
                bool limitToList,
                string lookupList,
                bool required,
                bool locked,
                DisplayModeConstants displayMode,
                string weightField)
                : this()
            {
                Name = name;
                Type = type;
                DefaultValue = defaultvalue.ToString();
                DisplayInProperties = displayInProps;
                Group = group;
                Prompt = prompt;
                ValuesList = valuesList;
                Description = description;
                Format = format;
                LimitToList = limitToList;
                LookupList = lookupList;
                Required = required;
                Locked = locked;
                DisplayMode = displayMode;
                WeightField = weightField;
            }

            private static XProperties EnsurePrimaryXProperties(Primary primary)
            {
                XProperties xprops = null;

                if (primary != null)
                {
                    xprops = primary.XProperties;

                    if (xprops is null)
                    {
                        xprops = new XProperties();
                        primary.XProperties = xprops;
                    }
                }

                return xprops;
            }

            public void RemoveFromEntity(Primary primary)
            {
                DufDocument.XPropertyRemove(primary?.XProperties, Name);
            }

            public void SetOnEntity(Primary primary, object value)
            {
                object typedValue;

                switch (Type)
                {
                    case AttributeType.DateTime:

                        if (value is DateTime)
                        {
                            typedValue = (DateTime)value;
                        }
                        else if (value is String)
                        { 
                            // TODO This code seems reasonable, but when I created a date with the Deswik.CAD UI, the datetime seemed to be a string.
                            //typedValue = string.IsNullOrEmpty(value) ? DateTime.Now : DateTime.Parse(value);
                            typedValue = value;
                        }
                        else
                        {
                            throw new ArgumentException($"value must be a DateTime or a String, but is a {value.GetType()}");
                        }

                        break;

                    case AttributeType.Double:

                        if (value is double)
                        {
                            typedValue = (double)value;
                        }
                        else if (value is String && value.ToString() == "")
                        {
                            typedValue = value;
                        }
                        else
                        {
                            throw new ArgumentException($"value must be a Double, but is a {value.GetType()}");
                        }

                        break;

                    case AttributeType.Integer:

                        if (value is long)
                        {
                            typedValue = value;
                        }
                        else if (value is String && value.ToString() == "")
                        {
                            typedValue = value;
                        }
                        else
                        {
                            try
                            {
                                typedValue = long.Parse(value.ToString());
                            }
                            catch
                            {
                                throw new ArgumentException($"value must be an Integer, but is a {value.GetType()}");
                            }
                        }

                        break;

                    case AttributeType.String:
                        if (value is String)
                        {
                            typedValue = value;
                        }
                        else
                        {
                            throw new ArgumentException($"value must be a String, but is a {value.GetType()}");
                        }

                        break;

                    default:
                        throw new NotSupportedException($"{Type} not supported");
                }

                DufDocument.XPropertySet(EnsurePrimaryXProperties(primary), Name, typedValue);
            }

            public void SetOnEntity(Primary primary)
            {
                SetOnEntity(primary, DefaultValue);
            }

            internal static Attribute GetFromXProperties(XProperties xprops, AttributePropertyNames propertyNames)
            {
                var name = GetStringOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.Name, PropertyNamesAndDefaults);
                var type = TypeFromName(GetStringOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.Type, PropertyNamesAndDefaults));
                var defaultValue = GetObjectOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.DefaultValue, PropertyNamesAndDefaults);
                var displayInProps = GetBoolOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.DisplayInProperties, PropertyNamesAndDefaults);
                var group = GetStringOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.Group, PropertyNamesAndDefaults);
                var prompt = GetBoolOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.Prompt, PropertyNamesAndDefaults);
                var valuesList = GetStringOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.ValuesList, PropertyNamesAndDefaults);
                var description = GetStringOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.Description, PropertyNamesAndDefaults);
                var format = GetStringOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.Format, PropertyNamesAndDefaults);
                var limitToList = GetBoolOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.LimitToList, PropertyNamesAndDefaults);
                var lookupList = GetStringOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.LookupList, PropertyNamesAndDefaults);
                var required = GetBoolOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.Required, PropertyNamesAndDefaults);
                var locked = GetBoolOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.Locked, PropertyNamesAndDefaults);
                var displayMode = (DisplayModeConstants)GetIntOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.DisplayMode, PropertyNamesAndDefaults);
                var weightField = GetStringOrDefaultFromXProps(xprops, propertyNames, AttributePropertyNames.WeightField, PropertyNamesAndDefaults);

                return new Attribute(name, type, defaultValue, displayInProps, group, prompt, valuesList, description, format, limitToList, lookupList, required, locked, displayMode, weightField);
            }

            internal void SetInXProperties(XProperties xprops, AttributePropertyNames propertyNames)
            {
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.Name, Name);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.Type, NameFromType(Type));
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.DefaultValue, DefaultValue);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.DisplayInProperties, DisplayInProperties);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.Group, Group);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.Prompt, Prompt);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.ValuesList, ValuesList);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.Description, Description);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.Format, Format);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.LimitToList, LimitToList);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.LookupList, LookupList);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.Required, Required);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.Locked, Locked);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.DisplayMode, (int)DisplayMode);
                SetValueInXProps(xprops, propertyNames, AttributePropertyNames.WeightField, WeightField);
            }

            internal static void RemoveFromXProperties(XProperties xprops, AttributePropertyNames propertyNames)
            {
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.Name);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.Type);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.DefaultValue);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.DisplayInProperties);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.Group);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.Prompt);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.ValuesList);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.Description);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.Format);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.LimitToList);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.LookupList);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.Required);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.Locked);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.DisplayMode);
                RemoveFromXProps(xprops, propertyNames, AttributePropertyNames.WeightField);
            }

            private static bool GetBoolOrDefaultFromValue(object value, bool defaultValue)
            {
                if (!(value is bool b))
                {
                    if (!bool.TryParse(value.ToString(), out b))
                    {
                        b = defaultValue;
                    }
                }

                return b;
            }

            private static string GetStringOrDefaultFromValue(object value, string defaultValue)
            {
                if (!(value is string s))
                {
                    s = value is null ? defaultValue : value.ToString();
                }

                return s;
            }

            private static int GetIntOrDefaultFromValue(object value, int defaultValue)
            {
                if (!(value is int i))
                {
                    if (!int.TryParse(value.ToString(), out i))
                    {
                        i = defaultValue;
                    }
                }

                return i;
            }

            private static bool GetBoolOrDefaultFromXProp(XProperty xprop, bool defaultValue)
            {
                return xprop?.Value.Count > 0 ? GetBoolOrDefaultFromValue(xprop.Value[0].Value, defaultValue) : defaultValue;
            }

            private static int GetIntOrDefaultFromXProp(XProperty xprop, int defaultValue)
            {
                return xprop?.Value.Count > 0 ? GetIntOrDefaultFromValue(xprop.Value[0].Value, defaultValue) : defaultValue;
            }

            private static object GetObjectOrDefaultFromXProp(XProperty xprop, object defaultValue)
            {
                return xprop?.Value.Count > 0 ? xprop.Value[0].Value : defaultValue;
            }

            private static string GetStringOrDefaultFromXProp(XProperty xprop, string defaultValue)
            {
                return xprop?.Value.Count > 0 ? GetStringOrDefaultFromValue(xprop.Value[0].Value, defaultValue) : defaultValue;
            }

            private static bool GetBoolOrDefaultFromXProps(XProperties xprops, AttributePropertyNames propertyNames, string propertyName, Dictionary<string, object> defaultValues)
            {
                return GetBoolOrDefaultFromXProp(DufDocument.XPropertyGet(xprops, propertyNames.GetPropertyName(propertyName), false), (bool)defaultValues[propertyName]);
            }

            private static int GetIntOrDefaultFromXProps(XProperties xprops, AttributePropertyNames propertyNames, string propertyName, Dictionary<string, object> defaultValues)
            {
                return GetIntOrDefaultFromXProp(DufDocument.XPropertyGet(xprops, propertyNames.GetPropertyName(propertyName), false), (int)defaultValues[propertyName]);
            }

            private static object GetObjectOrDefaultFromXProps(XProperties xprops, AttributePropertyNames propertyNames, string propertyName, Dictionary<string, object> defaultValues)
            {
                return GetObjectOrDefaultFromXProp(DufDocument.XPropertyGet(xprops, propertyNames.GetPropertyName(propertyName), false), defaultValues[propertyName]);
            }

            private static string GetStringOrDefaultFromXProps(XProperties xprops, AttributePropertyNames propertyNames, string propertyName, Dictionary<string, object> defaultValues)
            {
                return GetStringOrDefaultFromXProp(DufDocument.XPropertyGet(xprops, propertyNames.GetPropertyName(propertyName), false), defaultValues[propertyName].ToString());
            }

            private bool GetBoolOrDefault(string propertyName)
            {
                var value = _propertyValues[propertyName];

                if (!(value is bool b))
                {
                    if (!bool.TryParse(value.ToString(), out b))
                    {
                        b = (bool)PropertyNamesAndDefaults[propertyName];
                    }
                }

                return b;
            }

            private int GetIntOrDefault(string propertyName)
            {
                var value = _propertyValues[propertyName];

                if (!(value is int i))
                {
                    if (!int.TryParse(value.ToString(), out i))
                    {
                        i = (int)PropertyNamesAndDefaults[propertyName];
                    }
                }

                return i;
            }

            private string GetStringOrDefault(string propertyName)
            {
                var value = _propertyValues[propertyName];

                if (!(value is string s))
                {
                    s = PropertyNamesAndDefaults[propertyName].ToString();
                }

                return s;
            }

            private static void SetValueInXProps(XProperties xprops, AttributePropertyNames propertyNames, string propertyName, object value)
            {
                DufDocument.XPropertySet(xprops, propertyNames.GetPropertyName(propertyName), value);
            }

            private static void RemoveFromXProps(XProperties xprops, AttributePropertyNames propertyNames, string propertyName)
            {
                DufDocument.XPropertyRemove(xprops, propertyNames.GetPropertyName(propertyName));
            }
        }

        public enum AttributesType
        {
            Standard,
            Vert
        }
    }
}
