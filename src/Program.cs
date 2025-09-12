using System;
using System.IO;
using SimpleDuf;
using Deswik.Entities.Cad;
using Deswik.Entities;
using Deswik.Duf;
using Deswik.Serialization;
using System.Collections.Generic;
using System.Reflection;
using System.Linq;

namespace ConsoleAppNet46
{
    class Program
    {
        static Program()
        {
            AppDomain.CurrentDomain.AssemblyResolve += MyResolveEventHandler;
        }

        private static Assembly MyResolveEventHandler(object sender, ResolveEventArgs args)
        {
            string requestedAssemblyNameSimple = new AssemblyName(args.Name).Name;
            string deswik_install_path = @"C:\DeswikSoftware\DeswikSuite\Binaries\Release64";

            if (!Directory.Exists(deswik_install_path))
            {
                deswik_install_path = @"C:\Program Files\Deswik\Deswik.Suite 2024.1";
            }

            string fullPathToAssembly = Path.Combine(deswik_install_path, requestedAssemblyNameSimple + ".dll");
            if (File.Exists(fullPathToAssembly))
            {
                Assembly assembly = Assembly.LoadFrom(fullPathToAssembly);
                return assembly;
            }
            return null;
        }

        static void Main(string[] args)
        {
            var source_duf = args[0];
            var dest_duf = args[1];

            string new_key = "new_key";
            string new_value = "new_value";

            // Setup the .duf file
            File.Copy(source_duf, dest_duf, true);

            using (var docBefore = new DufDocument(dest_duf))
            {
                docBefore.Load();

                Layer layer = docBefore.GetLayerByName("0");
                var layer_xprops_before = layer.XProperties;

                Console.WriteLine($"Key present before: {layer_xprops_before.ContainsKey(new_key)}");

                // Trying to edit XProperties
                var props_list = new List<PropValue>();
                props_list.Add(new PropValue(new_value));
                var xprop = new XProperty() { Name = new_key, /* NOTE: XProperty must be named! */ Value = props_list };
                layer_xprops_before.Add(new_key, xprop);
                var new_key_exists = layer.XProperties.ContainsKey(new_key);
                var new_keys_value = new_key_exists ? layer.XProperties[new_key].Value.First().Value : "";

                // Confirmed it's set in memory
                Console.WriteLine($"Key present after: {new_key_exists}, value is '{new_keys_value}'");

                // Trying to save changes
                docBefore.Save();
            }

            // Reload the file.
            using (var docAfter = new DufDocument(dest_duf))
            {
                docAfter.Load();

                Layer layer = docAfter.GetLayerByName("0");
                var new_key_exists = layer.XProperties.ContainsKey(new_key);
                var new_keys_value = new_key_exists ? layer.XProperties[new_key].Value.First().Value : "";

                Console.WriteLine($"Key present after reload: {new_key_exists}, value is '{new_keys_value}'");
            }
        }
    }
}
